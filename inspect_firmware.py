#!/usr/bin/env python3
"""Read-only inspection of a Sokkia iM-series firmware update."""

from __future__ import annotations

import hashlib
import math
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

FIRMWARE = Path(
    "im_series_optical_firmware_v32/"
    "GMiM100_50_Update_Ver32.bin"
)

SIGNATURES = {
    "ELF executable or shared library": b"\x7fELF",
    "Windows executable marker": b"MZ",
    "ZIP archive member": b"PK\x03\x04",
    "7-Zip archive": b"\x37\x7a\xbc\xaf\x27\x1c",
    "gzip stream": b"\x1f\x8b\x08",
    "XZ compressed stream": b"\xfd7zXZ\x00",
    "Zstandard frame": b"\x28\xb5\x2f\xfd",
    "LZ4 frame": b"\x04\x22\x4d\x18",
    "SquashFS little-endian": b"hsqs",
    "SquashFS big-endian": b"sqsh",
    "U-Boot legacy image": b"\x27\x05\x19\x56",
    "FIT/FDT device tree": b"\xd0\x0d\xfe\xed",
    "CPIO newc archive": b"070701",
    "UBI image marker": b"UBI#",
    "PDF document": b"%PDF-",
}

KEYWORDS = (
    "linux", "busybox", "rootfs", "kernel", "u-boot", "uboot",
    "squashfs", "ext4", "arm", "aarch64", "mips", "x86",
    "copyright", "version", "update", "boot", "init",
    ".so", ".elf", ".ko", ".bin", "gzip", "lzma", "lz4",
    "zstd", "lzo", "filesystem", "system", "T200FF", "G1006",
)


def sha256(data: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(data)
    return digest.hexdigest()


def entropy(data: bytes) -> float:
    """Shannon entropy, measured in bits per byte."""
    if not data:
        return 0.0

    counts = Counter(data)
    size = len(data)

    return -sum(
        (count / size) * math.log2(count / size)
        for count in counts.values()
    )


def occurrences(
    data: bytes,
    signature: bytes,
    limit: int = 20,
) -> list[int]:
    """Find at most 'limit' occurrences of a byte signature."""
    offsets = []
    position = 0

    while len(offsets) < limit:
        position = data.find(signature, position)

        if position < 0:
            break

        offsets.append(position)
        position += 1

    return offsets


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else FIRMWARE

    if not path.is_file():
        print(f"ERROR: File not found: {path.resolve()}")
        print("Pass the firmware file path as the first argument.")
        return 1

    print(f"Reading: {path.resolve()}")
    data = path.read_bytes()
    size = len(data)

    report = [
        "SOKKIA FIRMWARE STATIC INSPECTION",
        "=" * 45,
        f"File: {path.resolve()}",
        f"Size: {size:,} bytes ({size / (1024 * 1024):.2f} MiB)",
        f"SHA-256: {sha256(data)}",
        "",
        "FIRST 256 BYTES",
        "-" * 45,
        data[:256].hex(" "),
        "",
        "HEADER AS ASCII",
        "-" * 45,
        repr(data[:128].decode("ascii", errors="replace")),
        "",
        "COMMON EMBEDDED FILE SIGNATURES",
        "-" * 45,
    ]

    for name, signature in SIGNATURES.items():
        offsets = occurrences(data, signature)

        if offsets:
            formatted = ", ".join(
                f"0x{offset:X} ({offset:,})"
                for offset in offsets
            )
            report.append(f"{name}: {formatted}")
        else:
            report.append(f"{name}: not found")

    report.extend([
        "",
        "ENTROPY",
        "-" * 45,
        f"Whole file: {entropy(data):.4f} bits/byte",
        "Entropy is a clue, not proof of compression or encryption.",
    ])

    chunk_size = 1024 * 1024

    for offset in range(0, size, chunk_size):
        chunk = data[offset:offset + chunk_size]
        report.append(
            f"Offset 0x{offset:X}: "
            f"{entropy(chunk):.4f} bits/byte "
            f"({len(chunk):,} bytes)"
        )

    report.extend([
        "",
        "AVAILABLE ANALYSIS TOOLS",
        "-" * 45,
    ])

    for tool in ("7z", "7zz", "7za", "binwalk", "strings", "file"):
        report.append(
            f"{tool}: {shutil.which(tool) or 'not found on PATH'}"
        )

    report.extend([
        "",
        "INTERESTING ASCII STRINGS",
        "-" * 45,
    ])

    string_pattern = re.compile(rb"[\x20-\x7e]{5,}")
    all_strings = []
    interesting_strings = []

    for match in string_pattern.finditer(data):
        value = match.group().decode("ascii", errors="replace")
        line = f"0x{match.start():08X}  {value}"

        all_strings.append(line)

        lower = value.lower()
        if any(keyword.lower() in lower for keyword in KEYWORDS):
            interesting_strings.append(line)

    report.append(f"ASCII strings found: {len(all_strings):,}")
    report.append(
        f"Strings matching investigation keywords: "
        f"{len(interesting_strings):,}"
    )

    report.extend(interesting_strings[:300])

    report_path = path.parent / "firmware_report.txt"
    strings_path = path.parent / "firmware_strings.txt"

    report_path.write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
    )
    strings_path.write_text(
        "\n".join(all_strings) + "\n",
        encoding="utf-8",
    )

    print("\nInspection complete.")
    print(f"Report:  {report_path.resolve()}")
    print(f"Strings: {strings_path.resolve()}")
    print("\nThis script only reads the firmware and writes reports.")
    print("It does not execute or modify the firmware.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())