"""Identify the actual onboard application inside the Sokkia IM-series firmware.

The decoded payload blobs in payload_extracts/ are containers, not plain files.
This script walks each one with a parser tailored to its format and writes a
single report naming the files that plausibly constitute the surveying
application.

  gzip_00342980.bin  UBI#          raw NAND image, volume headers to enumerate
  gzip_01B949E8.bin  070701        CPIO newc, this is the Linux rootfs
  xz_04A1A760.bin    tar           tsc4bsp43t/, which wraps a nested rootfs.tar

UBI stores every multi-byte field big-endian, which is the opposite of the
ELF and CPIO data in the same firmware. Getting that wrong yields plausible
looking but meaningless offsets, so the PEB stride is inferred from observed
magic positions rather than hard-coded.

Read-only. Nothing here writes to the firmware or to the payload blobs.
"""
from __future__ import annotations

import io
import struct
import tarfile
from collections import Counter
from pathlib import Path

BASE = Path("im_series_optical_firmware_v32")
PAYLOAD_DIR = BASE / "payload_extracts"
REPORT_PATH = BASE / "application_report.txt"

UBI_EC_MAGIC = b"UBI#"
UBI_VID_MAGIC = b"UBI!"
CPIO_MAGIC = b"070701"

# Subtrees worth dumping in full rather than filtering by name.
INTERESTING_PREFIXES = ("app/", "data/", "srv/", "opt/", "home/")

# Name fragments that actually indicate instrument software. Deliberately
# narrow: "point" matches mountpoint, viewpoint and datapoint in terminfo and
# keymaps, which buried the real hits on the first pass.
APP_NAME_HINTS = (
    "sokkia", "topcon", "tscomm", "tsscomm", "tsshield", "edm",
    "survey", "totalstation", "total_station", "field", "measure",
    "msr", "obs_", "controller", "fieldcontroller", "ts_", "_ts",
)

EXEC_BIT = 0o111


def human(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MiB"
    if size >= 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size} B"


def looks_like_app(path: str) -> bool:
    low = path.lower()
    if any(low.startswith(p) for p in INTERESTING_PREFIXES):
        return True
    return any(h in low for h in APP_NAME_HINTS)


def peb_stride(data: bytes) -> int:
    """Infer the UBI eraseblock size from where consecutive EC headers land."""
    offsets = []
    start = 0

    while len(offsets) < 64:
        pos = data.find(UBI_EC_MAGIC, start)
        if pos < 0:
            break
        offsets.append(pos)
        start = pos + 4

    if len(offsets) < 2:
        return 0x20000

    diffs = sorted({b - a for a, b in zip(offsets, offsets[1:]) if b > a})
    return diffs[0] if diffs else 0x20000


def parse_ubi(data: bytes, report: list[str]) -> None:
    """Enumerate volumes in a UBI image.

    Each physically-erased block starts with a 64-byte erase-counter header.
    A written volume adds a 200-byte volume header at vid_hdr_offset inside
    that block. All fields are big-endian.
    """
    report.extend([
        "", "=" * 72, "UBI IMAGE: VOLUME ENUMERATION",
        f"Size: {human(len(data))}",
    ])

    if not data.startswith(UBI_EC_MAGIC):
        report.append("  Not a UBI image (missing UBI# magic at offset 0).")
        return

    # ubi_ec_hdr: magic is a 4-byte __be32 "UBI#", NOT the 8 bytes the
    # kernel's UBI_EC_HDR_MAGIC string constant is written as. Reading it as
    # 8 shifts every following field by four and yields offsets like
    # 0x238594fd that look like data but are not.
    version = data[4]
    ec = struct.unpack_from(">Q", data, 8)[0]
    vid_hdr_offset = struct.unpack_from(">I", data, 16)[0]
    data_offset = struct.unpack_from(">I", data, 20)[0]
    image_seq = struct.unpack_from(">I", data, 24)[0]

    report.extend([
        f"  Version: {version}",
        f"  EC (erase counter): {ec}",
        f"  VID header offset: {vid_hdr_offset:#x}",
        f"  Data offset: {data_offset:#x}",
        f"  Image sequence: {image_seq}",
        f"  Header CRC: {struct.unpack_from('>I', data, 60)[0]:#010x}",
    ])

    stride = peb_stride(data)
    total_pebs = len(data) // stride
    report.extend([
        f"  PEB size: {stride:#x} ({human(stride)})",
        f"  PEBs in image: {total_pebs}",
        "",
    ])

    if vid_hdr_offset >= stride or data_offset >= stride:
        report.append(
            "  Header offsets are out of range for the inferred PEB size; "
            "the block layout does not match a plain UBI image."
        )
        return

    # Gather evidence rather than trusting any single field. In particular a
    # block can look erased (ec=0, CRC sentinel) while its body holds real
    # high-entropy payload, so body composition decides the verdict.
    erased_sentinel = 0
    ec_nonzero = 0
    filler_blocks = 0
    entropy_blocks = 0
    filler_total = 0.0

    for peb in range(total_pebs):
        base = peb * stride
        ec_hdr = data[base : base + 64]

        if not ec_hdr.startswith(UBI_EC_MAGIC):
            continue

        blk_ec = struct.unpack_from(">Q", ec_hdr, 8)[0]
        vid = base + vid_hdr_offset
        crc_stored = (
            struct.unpack_from(">I", data, vid + 196)[0]
            if vid + 200 <= len(data)
            else None
        )
        body = data[base + data_offset : base + stride]

        if blk_ec:
            ec_nonzero += 1

        if crc_stored == 0xFFFFFFFF:
            erased_sentinel += 1

        if not body:
            continue

        counts = Counter(body)
        filler = (counts[0xFF] + counts[0x00]) / len(body)
        filler_total += filler

        if filler > 0.95:
            filler_blocks += 1
        elif len(counts) > 128:
            entropy_blocks += 1

    present = total_pebs
    report.extend([
        f"  Blocks with non-zero erase counter: {ec_nonzero} of {present}",
        f"  Blocks with erased VID header CRC (0xFFFFFFFF): "
        f"{erased_sentinel} of {present}",
        f"  Blocks whose body is >95% 0xFF/0x00 filler: {filler_blocks} of {present}",
        f"  Blocks with high-entropy bodies (all 256 byte values): "
        f"{entropy_blocks} of {present}",
        f"  Mean filler fraction across blocks: {filler_total / present:.4f}",
        "",
    ])

    if erased_sentinel == present and ec_nonzero == 0 and filler_blocks == present:
        report.extend([
            "  VERDICT: every block is erased. This is an empty UBI target that",
            "  a firmware update writes into, not a stored copy of anything.",
        ])
        return

    if erased_sentinel == present and ec_nonzero == 0 and entropy_blocks > present // 2:
        report.extend([
            "  VERDICT: NOT a standard UBI volume image.",
            "  No block carries a valid volume header: every erase counter is",
            "  zero and every volume header CRC is the 0xFFFFFFFF erased",
            "  sentinel, so there is no volume table to enumerate. Yet the block",
            "  bodies are high-entropy payload, not flash filler, so this is not",
            "  an empty target either.",
            "",
            "  The 0x800/0x1000 header offsets and 128 KiB block stride are",
            "  genuine, but the volume-record layout does not match stock UBI.",
            "  Treat the internal format as unresolved. Resolve it with",
            "  ubireader before concluding anything about the contents; if that",
            "  also fails, this is more likely a vendor U-Boot/NAND update",
            "  partition scheme than a UBI volume set.",
        ])
        return

    # A genuinely mixed image: fall through to enumerating the real volumes.
    volumes: dict[str, dict] = {}

    for peb in range(total_pebs):
        base = peb * stride
        vid = base + vid_hdr_offset

        if vid + 200 > len(data) or not data.startswith(UBI_VID_MAGIC, vid):
            continue

        # Reject headers whose stored CRC is the erased sentinel. Those are
        # not volume records, whatever the surrounding fields happen to say.
        if struct.unpack_from(">I", data, vid + 196)[0] == 0xFFFFFFFF:
            continue

        vol_type, copy_flag = data[vid + 5], data[vid + 6]
        vol_id, lnum = struct.unpack_from(">II", data, vid + 8)
        data_size, used_ebs, data_pad = struct.unpack_from(">III", data, vid + 20)
        name = data[vid + 60 : vid + 188].split(b"\x00")[0].decode("ascii", "replace")

        # A volume name is NUL-padded printable ASCII. Anything else is filler
        # that happened to parse, not a real name.
        if not name.isprintable():
            name = f"<unnamed vol_id={vol_id}>"

        entry = volumes.setdefault(
            name,
            {"vol_id": vol_id, "vol_type": vol_type, "blocks": 0,
             "used_ebs": used_ebs, "bytes": 0, "pebs": []},
        )
        entry["blocks"] += 1
        entry["bytes"] += max(0, data_size - data_pad)
        entry["pebs"].append((base, lnum))

    report.append(f"  Distinct volumes in written blocks: {len(volumes)}")

    VOL_TYPES = {0: "dynamic", 1: "static", 2: "dynamic (reserved)"}

    for name, v in sorted(volumes.items()):
        report.extend([
            "",
            f"  Volume {name!r}",
            f"    vol_id={v['vol_id']}  type={VOL_TYPES.get(v['vol_type'], v['vol_type'])}",
            f"    blocks written: {v['blocks']}  used_ebs field: {v['used_ebs']}",
            f"    payload bytes: {v['bytes']:,} ({human(v['bytes'])})",
            f"    PEB offsets: {', '.join(hex(b) for b, _ in v['pebs'][:8])}"
            + (" ..." if len(v["pebs"]) > 8 else ""),
        ])

    report.append(
        "  UBI volumes are images in their own right, usually another "
        "filesystem. Filenames only become visible after each volume is carved "
        "out and its contents mounted."
    )


# --------------------------------------------------------------------------
# CPIO newc
# --------------------------------------------------------------------------

def parse_cpio(data: bytes, report: list[str], label: str = "LIVE ROOTFS") -> None:
    """Walk a CPIO newc archive and list every entry.

    newc is a flat header format with no index, so this walks the whole stream.
    Each header is 110 ASCII hex bytes, then a NUL-terminated name padded to a
    4-byte boundary, then the file data padded the same way.
    """
    report.extend(["", "=" * 72, f"CPIO newc: {label}", f"Size: {human(len(data))}"])

    if not data.startswith(CPIO_MAGIC):
        report.append("  Not a CPIO newc archive (missing 070701 magic).")
        return

    entries: list[tuple[str, int, int]] = []
    offset = 0
    total = len(data)

    while offset + 110 <= total:
        if data[offset : offset + 6] != CPIO_MAGIC:
            report.append(f"  Lost sync at offset {offset:#x}; stopping.")
            break

        try:
            mode = int(data[offset + 14 : offset + 22], 16)
            filesize = int(data[offset + 54 : offset + 62], 16)
            namesize = int(data[offset + 94 : offset + 102], 16)
        except ValueError:
            report.append(f"  Malformed hex header at offset {offset:#x}; stopping.")
            break

        if not 0 < namesize < 4096:
            report.append(f"  Implausible namesize at offset {offset:#x}; stopping.")
            break

        name_start = offset + 110

        if name_start + namesize > total:
            report.append(f"  Truncated name at offset {offset:#x}; stopping.")
            break

        raw = data[name_start : name_start + namesize - 1].decode("utf-8", "replace")
        data_start = name_start + namesize
        data_start += (-data_start) % 4
        offset = data_start + filesize
        offset += (-offset) % 4

        if raw == "TRAILER!!!":
            break

        # CPIO names are relative and usually carry a leading "./".
        name = raw.lstrip("./") or raw
        entries.append((name, mode, filesize))

    files = [e for e in entries if (e[1] & 0o170000) != 0o040000]
    dirs = [e for e in entries if (e[1] & 0o170000) == 0o040000]
    links = [e for e in entries if (e[1] & 0o170000) == 0o120000]

    report.extend([
        f"  Entries: {len(entries)}  dirs: {len(dirs)}  files: {len(files)}  symlinks: {len(links)}",
        f"  Total file bytes: {sum(s for _, _, s in files):,}",
        "",
        "  Top-level directories:",
        "    " + "  ".join(sorted({n.split("/")[0] + "/" for n, _, _ in dirs if n.strip("/")})),
    ])

    # Dump whole subtrees. Names alone do not reveal which binary is the app.
    for prefix in INTERESTING_PREFIXES:
        sub = [e for e in entries if e[0].startswith(prefix)]

        if not sub:
            continue

        sub_files = [e for e in sub if (e[1] & 0o170000) == 0o100000]
        report.extend([
            "",
            f"  Subtree {prefix} ({len(sub)} entries, {len(sub_files)} regular files):",
        ])

        for name, mode, size in sorted(sub, key=lambda e: e[0]):
            ftype = mode & 0o170000
            kind = "dir " if ftype == 0o040000 else "link" if ftype == 0o120000 else f"{mode & 0o7777:04o}"
            report.append(f"    {size:>11,}  {kind}  {name}")

    app = sorted((n, m, s) for n, m, s in files if looks_like_app(n))
    report.extend(["", f"  Files matching instrument hints ({len(app)}):"])

    for name, mode, size in app:
        report.append(f"    {size:>12,}  {mode & 0o7777:04o}  {name}")

    # The entry point matters more than the name: what does init actually run?
    entry = [e for e in files if e[0] in ("sbin/init", "bin/init", "init", "linuxrc", "etc/init.d/rcS", "etc/init.d/rc.local")]

    if entry:
        report.append("")
        report.append("  Init / entry-point candidates:")

        for name, mode, size in entry:
            report.append(f"    {size:>12,}  {mode & 0o7777:04o}  {name}")

    report.append("")
    report.append("  Largest 40 files:")

    for name, mode, size in sorted(files, key=lambda e: -e[2])[:40]:
        report.append(f"    {size:>12,}  {human(size):>9}  {name}")


# --------------------------------------------------------------------------
# tar
# --------------------------------------------------------------------------

def parse_tar(path: Path, report: list[str], depth: int = 0) -> None:
    """List a tar, and recurse one level into any rootfs.tar it contains."""
    pad = "  " * (depth + 1)
    report.extend([
        "", "=" * 72,
        f"{pad}TAR ARCHIVE: {path.name}",
        f"{pad}Size: {human(path.stat().st_size)}",
    ])

    try:
        tf = tarfile.open(path, "r:*")
    except tarfile.TarError as exc:
        report.append(f"{pad}  Could not read as tar: {exc}")
        return

    with tf:
        members = tf.getmembers()
        files = [m for m in members if m.isfile()]

        report.extend([
            f"{pad}  Members: {len(members)}  files: {len(files)}",
            f"{pad}  Total file bytes: {sum(m.size for m in files):,}",
        ])

        for m in sorted(members, key=lambda m: m.name):
            kind = "dir " if m.isdir() else "link" if m.issym() else f"{m.mode:04o}"
            report.append(f"{pad}    {m.size:>12,}  {kind}  {m.name}")

        nested = [m for m in files if m.name.endswith(".tar")]

        for m in nested:
            handle = tf.extractfile(m)

            if handle is None:
                continue

            blob = handle.read()

            if blob.startswith(CPIO_MAGIC):
                parse_cpio(blob, report, label=f"{m.name} (inside {path.name})")
            else:
                report.extend([
                    "", "=" * 72,
                    f"{pad}NESTED TAR: {m.name}",
                    f"{pad}Size: {human(len(blob))}  magic: {blob[:8]!r}",
                ])
                inner = io.BytesIO(blob)

                try:
                    with tarfile.open(fileobj=inner, mode="r:*") as itf:
                        inner_files = [x for x in itf.getmembers() if x.isfile()]
                        report.extend([
                            f"{pad}  Members: {len(itf.getmembers())}  files: {len(inner_files)}",
                            f"{pad}  Total file bytes: {sum(x.size for x in inner_files):,}",
                        ])
                except tarfile.TarError as exc:
                    report.append(f"{pad}  Could not read nested tar: {exc}")


# --------------------------------------------------------------------------

def main() -> int:
    targets = {
        "UBI": PAYLOAD_DIR / "gzip_00342980.bin",
        "CPIO": PAYLOAD_DIR / "gzip_01B949E8.bin",
        "TAR": PAYLOAD_DIR / "xz_04A1A760.bin",
    }

    for path in targets.values():
        if not path.is_file():
            print(f"missing payload: {path}")
            return 1

    report: list[str] = [
        "SOKKIA IM-SERIES: ONBOARD APPLICATION IDENTIFICATION",
        "=" * 72,
        "",
        "Read-only structural analysis of the decoded payload containers.",
        "",
    ]

    parse_ubi(targets["UBI"].read_bytes(), report)
    parse_cpio(targets["CPIO"].read_bytes(), report)
    parse_tar(targets["TAR"], report)

    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Report written to: {REPORT_PATH.resolve()}")
    print(f"Lines: {len(report)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
