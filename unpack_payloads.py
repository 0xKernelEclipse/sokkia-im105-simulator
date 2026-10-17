from __future__ import annotations

import gzip
import hashlib
import lzma
import re
import struct
import zlib
from pathlib import Path

BASE = Path("im_series_optical_firmware_v32")
FIRMWARE = BASE / "GMiM100_50_Update_Ver32.bin"
ELF_DIR = BASE / "elf_extracts"
OUT_DIR = BASE / "payload_extracts"

MAX_OUTPUT = 256 * 1024 * 1024  # 256 MiB per extracted stream

SIGNATURES = {
    "ELF": b"\x7fELF",
    "gzip": b"\x1f\x8b\x08",
    "XZ": b"\xfd7zXZ\x00",
    "ZIP": b"PK\x03\x04",
    "SquashFS": b"hsqs",
    "SquashFS big-endian": b"sqsh",
    "Device tree": b"\xd0\x0d\xfe\xed",
    "U-Boot legacy image": b"\x27\x05\x19\x56",
    "CPIO newc": b"070701",
    "UBI": b"UBI#",
}

KEYWORDS = (
    "linux", "kernel", "rootfs", "squashfs", "busybox",
    "tsshield", "tsscomm", "sokkia", "topcon", "survey",
    "measurement", "angle", "distance", "coordinate",
    "edm", "update", "firmware", "boot", "arm",
    "version", ".so", ".bin", "zimage", "gt100",
    "/app/", "/usr/", "/lib/", "rootfs", "init",
)


def find_offsets(data: bytes, needle: bytes, limit: int = 30) -> list[int]:
    offsets = []
    start = 0

    while len(offsets) < limit:
        pos = data.find(needle, start)
        if pos < 0:
            break
        offsets.append(pos)
        start = pos + 1

    return offsets


def extract_gzip(data: bytes, offset: int) -> tuple[bytes, int]:
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    output = decoder.decompress(data[offset:], MAX_OUTPUT + 1)

    if len(output) > MAX_OUTPUT or decoder.unconsumed_tail:
        raise ValueError("Output exceeded 256 MiB safety limit")

    if not decoder.eof:
        raise ValueError("Incomplete stream or not a valid gzip stream")

    consumed = len(data) - offset - len(decoder.unused_data)
    return output, consumed


def extract_xz(data: bytes, offset: int) -> tuple[bytes, int]:
    decoder = lzma.LZMADecompressor(
        format=lzma.FORMAT_AUTO,
        memlimit=256 * 1024 * 1024,
    )

    output = decoder.decompress(data[offset:], max_length=MAX_OUTPUT + 1)

    if len(output) > MAX_OUTPUT:
        raise ValueError("Output exceeded 256 MiB safety limit")

    if not decoder.eof:
        raise ValueError("Incomplete stream or output safety limit reached")

    consumed = len(data) - offset - len(decoder.unused_data)
    return output, consumed


def summarize_blob(path: Path, data: bytes, report: list[str]) -> None:
    report.extend([
        "",
        "=" * 65,
        f"FILE: {path}",
        f"Size: {len(data):,} bytes",
        f"SHA-256: {hashlib.sha256(data).hexdigest()}",
        f"First 32 bytes: {data[:32].hex(' ')}",
        "Embedded signatures:",
    ])

    for name, signature in SIGNATURES.items():
        offsets = find_offsets(data, signature, limit=10)
        if offsets:
            report.append(
                f"  {name}: "
                + ", ".join(f"0x{x:X}" for x in offsets)
            )

    strings = []

    for match in re.finditer(rb"[\x20-\x7e]{5,}", data):
        value = match.group().decode("ascii", errors="replace")

        if any(k.lower() in value.lower() for k in KEYWORDS):
            strings.append(f"  0x{match.start():08X}: {value}")

    report.append(f"Relevant readable strings: {len(strings)}")
    report.extend(strings[:100])


def main() -> int:
    if not FIRMWARE.is_file():
        print(f"Firmware not found: {FIRMWARE.resolve()}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    data = FIRMWARE.read_bytes()
    report = [
        "READ-ONLY EMBEDDED PAYLOAD INSPECTION",
        f"Firmware: {FIRMWARE.resolve()}",
        f"Size: {len(data):,} bytes",
        "",
    ]

    # Inspect the two ELF files already extracted.
    if ELF_DIR.is_dir():
        for path in sorted(ELF_DIR.glob("elf_*.bin")):
            try:
                summarize_blob(path, path.read_bytes(), report)
            except OSError as exc:
                report.append(f"Unable to read {path}: {exc}")

    # Attempt validated extraction of embedded gzip and XZ streams.
    candidates = []

    for signature, kind in (
        (b"\x1f\x8b\x08", "gzip"),
        (b"\xfd7zXZ\x00", "xz"),
    ):
        for offset in find_offsets(data, signature):
            candidates.append((offset, kind))

    report.extend([
        "",
        "=" * 65,
        "COMPRESSED STREAM INVESTIGATION",
        f"Candidate signatures found: {len(candidates)}",
    ])

    for offset, kind in candidates:
        report.append(f"\nTrying {kind} at offset 0x{offset:X}")

        try:
            if kind == "gzip":
                output, consumed = extract_gzip(data, offset)
            else:
                output, consumed = extract_xz(data, offset)

            if len(output) < 100:
                raise ValueError("Decoded output is suspiciously small")

            target = OUT_DIR / f"{kind}_{offset:08X}.bin"
            target.write_bytes(output)

            report.append("  Result: valid completed stream")
            report.append(f"  Compressed bytes consumed: {consumed:,}")
            report.append(f"  Decoded bytes: {len(output):,}")
            report.append(f"  Saved to: {target.resolve()}")

            summarize_blob(target, output, report)

        except (
            ValueError,
            zlib.error,
            lzma.LZMAError,
            EOFError,
            MemoryError,
        ) as exc:
            report.append(f"  Not extracted: {exc}")

    report_path = OUT_DIR / "payload_report.txt"
    report_path.write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
    )

    print("\n".join(report))
    print(f"\nFull report saved to: {report_path.resolve()}")
    print("The original firmware was not modified or executed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())