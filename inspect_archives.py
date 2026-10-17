from __future__ import annotations

import io
import re
import tarfile
from collections import Counter
from pathlib import Path

BASE = Path("im_series_optical_firmware_v32")
PAYLOADS = BASE / "payload_extracts"

CPIO_FILE = PAYLOADS / "gzip_01B949E8.bin"
PACKAGE_FILE = PAYLOADS / "xz_04A1A760.bin"
UBI_FILE = PAYLOADS / "gzip_00342980.bin"

REPORT_FILE = PAYLOADS / "archive_listing.txt"

KEYWORDS = (
    "sokkia", "topcon", "tsshield", "tscomm", "edm",
    "survey", "instrument", "measurement", "coordinate",
    "stakeout", "station", "display", "screen", "panel",
    "gui", "qml", "qt", "font", "g1006", "gt100",
    "application", "mainmenu", "totalstation", "total_station",
)

SIGNATURES = {
    "ELF executable": b"\x7fELF",
    "SquashFS little-endian": b"hsqs",
    "SquashFS big-endian": b"sqsh",
    "UBI image": b"UBI#",
    "gzip stream": b"\x1f\x8b\x08",
    "XZ stream": b"\xfd7zXZ\x00",
    "ZIP member": b"PK\x03\x04",
}


def add(report: list[str], text: str = "") -> None:
    report.append(text)


def is_interesting(name: str) -> bool:
    lower = name.lower()
    return any(keyword in lower for keyword in KEYWORDS)


def parse_newc(data: bytes, report: list[str]) -> None:
    """List a newc CPIO archive without extracting its files."""
    add(report, "\n" + "=" * 72)
    add(report, "CPIO ARCHIVE")
    add(report, "=" * 72)

    offset = 0
    count = 0
    total_file_bytes = 0
    interesting = []
    top_level = Counter()
    embedded = []
    trailer_found = False

    while offset + 110 <= len(data):
        header = data[offset:offset + 110]
        magic = header[:6]

        if magic not in (b"070701", b"070702"):
            add(
                report,
                f"Stopped at 0x{offset:X}: "
                f"unexpected header {header[:16]!r}",
            )
            break

        try:
            mode = int(header[14:22], 16)
            file_size = int(header[54:62], 16)
            name_size = int(header[94:102], 16)
        except ValueError:
            add(report, f"Invalid CPIO fields at 0x{offset:X}")
            break

        name_start = offset + 110
        name_end = name_start + name_size

        if name_size < 1 or name_end > len(data):
            add(report, f"Invalid filename length at 0x{offset:X}")
            break

        raw_name = data[name_start:name_end]
        name = raw_name.split(b"\x00", 1)[0].decode(
            "utf-8", errors="replace"
        )

        data_start = (name_end + 3) & ~3
        data_end = data_start + file_size

        if data_end > len(data):
            add(report, f"File exceeds archive at 0x{offset:X}: {name}")
            break

        entry_data = data[data_start:data_end]
        count += 1
        total_file_bytes += file_size

        parts = name.replace("\\", "/").strip("/").split("/")
        if parts and parts[0]:
            top_level[parts[0]] += 1

        if name == "TRAILER!!!":
            trailer_found = True
            break

        if is_interesting(name):
            interesting.append(
                f"{name} | size={file_size:,} | mode={mode:07o}"
            )

        # Look for nested images beginning exactly at the file boundary.
        for label, signature in SIGNATURES.items():
            if entry_data.startswith(signature):
                embedded.append(
                    f"{name} begins with {label}; size={file_size:,}"
                )

        offset = (data_end + 3) & ~3

    add(report, f"Entries parsed: {count:,}")
    add(report, f"Total declared file bytes: {total_file_bytes:,}")
    add(report, f"CPIO trailer found: {trailer_found}")
    add(report, f"Final parser offset: 0x{offset:X}")

    add(report, "\nTop-level path components:")
    for name, number in top_level.most_common(50):
        add(report, f"  {name}: {number}")

    add(report, "\nSurveying/application-related paths:")
    add(report, f"Matches: {len(interesting)}")
    for item in interesting[:250]:
        add(report, f"  {item}")

    add(report, "\nFiles beginning with embedded image signatures:")
    for item in embedded[:100]:
        add(report, f"  {item}")


def inspect_tar(
    data: bytes,
    label: str,
    report: list[str],
    inspect_nested_rootfs: bool = False,
) -> None:
    """List a TAR archive and optionally inspect rootfs.tar."""
    add(report, "\n" + "=" * 72)
    add(report, f"TAR ARCHIVE: {label}")
    add(report, "=" * 72)

    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
            members = archive.getmembers()
            add(report, f"Entries: {len(members):,}")

            for item in members[:100]:
                add(
                    report,
                    f"  {item.name} | size={item.size:,} "
                    f"| type={item.type!r}",
                )

            interesting = [
                item for item in members
                if is_interesting(item.name)
            ]

            add(report, f"\nRelevant path matches: {len(interesting)}")
            for item in interesting[:250]:
                add(
                    report,
                    f"  {item.name} | size={item.size:,}",
                )

            roots = Counter()
            for item in members:
                parts = item.name.strip("./").split("/")
                if parts and parts[0]:
                    roots[parts[0]] += 1

            add(report, "\nTop-level directories/files:")
            for name, number in roots.most_common(50):
                add(report, f"  {name}: {number}")

            if inspect_nested_rootfs:
                candidates = [
                    item for item in members
                    if item.name.lower().endswith("rootfs.tar")
                    and item.isfile()
                ]

                for item in candidates:
                    add(report, "\n" + "-" * 60)
                    add(report, f"NESTED FILESYSTEM ARCHIVE: {item.name}")
                    add(report, f"Declared size: {item.size:,} bytes")

                    source = archive.extractfile(item)
                    if source is None:
                        add(report, "Could not read nested archive.")
                        continue

                    nested_data = source.read()

                    try:
                        inspect_tar(
                            nested_data,
                            item.name,
                            report,
                            inspect_nested_rootfs=False,
                        )
                    except (tarfile.TarError, OSError, ValueError) as exc:
                        add(
                            report,
                            f"Nested file is not a readable TAR archive: "
                            f"{exc}",
                        )

    except (tarfile.TarError, OSError, ValueError) as exc:
        add(report, f"Could not parse as TAR: {exc}")


def main() -> int:
    report = [
        "SOKKIA FIRMWARE ARCHIVE INVESTIGATION",
        "Read-only; no firmware execution or installation.",
    ]

    if CPIO_FILE.is_file():
        parse_newc(CPIO_FILE.read_bytes(), report)
    else:
        add(report, f"Missing CPIO file: {CPIO_FILE}")

    if PACKAGE_FILE.is_file():
        inspect_tar(
            PACKAGE_FILE.read_bytes(),
            str(PACKAGE_FILE),
            report,
            inspect_nested_rootfs=True,
        )
    else:
        add(report, f"Missing package file: {PACKAGE_FILE}")

    if UBI_FILE.is_file():
        data = UBI_FILE.read_bytes()
        add(report, "\n" + "=" * 72)
        add(report, "UBI IMAGE SUMMARY")
        add(report, "=" * 72)
        add(report, f"Size: {len(data):,} bytes")
        add(report, f"First 64 bytes: {data[:64].hex(' ')}")

        for label, signature in SIGNATURES.items():
            offsets = [
                match.start()
                for match in re.finditer(
                    re.escape(signature), data
                )
            ][:20]

            if offsets:
                add(
                    report,
                    f"{label}: "
                    + ", ".join(f"0x{x:X}" for x in offsets),
                )
    else:
        add(report, f"Missing UBI file: {UBI_FILE}")

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
    )

    print("\n".join(report))
    print(f"\nFull report: {REPORT_FILE.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())