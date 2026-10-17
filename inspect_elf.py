from __future__ import annotations

import re
import struct
from pathlib import Path

FIRMWARE = Path(
    "im_series_optical_firmware_v32/"
    "GMiM100_50_Update_Ver32.bin"
)

OUTPUT = FIRMWARE.parent / "elf_extracts"
MAX_EXTRACT_SIZE = 32 * 1024 * 1024

MACHINE_NAMES = {
    3: "x86",
    40: "ARM",
    62: "x86-64",
    183: "AArch64",
}

TYPE_NAMES = {
    0: "NONE",
    1: "REL (relocatable)",
    2: "EXEC (executable)",
    3: "DYN (shared object / PIE)",
    4: "CORE",
}


def parse_elf(data: bytes, base: int) -> dict:
    ident = data[base:base + 16]

    if len(ident) != 16 or ident[:4] != b"\x7fELF":
        raise ValueError("Invalid ELF signature")

    elf_class = ident[4]
    encoding = ident[5]

    if encoding == 1:
        endian = "<"
        endian_name = "Little-endian"
    elif encoding == 2:
        endian = ">"
        endian_name = "Big-endian"
    else:
        raise ValueError(f"Unknown ELF byte order: {encoding}")

    if elf_class == 1:
        header_fmt = endian + "16sHHIIIIIHHHHHH"
        ph_fmt = endian + "IIIIIIII"
        bits = 32
    elif elf_class == 2:
        header_fmt = endian + "16sHHIQQQIHHHHHH"
        ph_fmt = endian + "IIQQQQQQ"
        bits = 64
    else:
        raise ValueError(f"Unknown ELF class: {elf_class}")

    header_size = struct.calcsize(header_fmt)

    if base + header_size > len(data):
        raise ValueError("Truncated ELF header")

    header = struct.unpack_from(header_fmt, data, base)

    (
        _ident,
        e_type,
        e_machine,
        _version,
        e_entry,
        e_phoff,
        e_shoff,
        _flags,
        e_ehsize,
        e_phentsize,
        e_phnum,
        e_shentsize,
        e_shnum,
        _shstrndx,
    ) = header

    ph_min_size = struct.calcsize(ph_fmt)

    if e_phnum > 1024:
        raise ValueError("Unreasonable program-header count")

    if e_shnum > 100000:
        raise ValueError("Unreasonable section-header count")

    if e_phnum and e_phentsize < ph_min_size:
        raise ValueError("Invalid program-header entry size")

    available = len(data) - base
    spans = [e_ehsize, header_size]
    interpreters = []
    load_segments = []

    ph_table_end = e_phoff + e_phnum * e_phentsize

    if e_phnum:
        if e_phoff > available or ph_table_end > available:
            raise ValueError("Program-header table exceeds file bounds")

        spans.append(ph_table_end)

        for i in range(e_phnum):
            pos = base + e_phoff + i * e_phentsize
            ph = struct.unpack_from(ph_fmt, data, pos)

            if elf_class == 1:
                (
                    p_type,
                    p_offset,
                    _vaddr,
                    _paddr,
                    p_filesz,
                    _memsz,
                    _flags,
                    _align,
                ) = ph
            else:
                (
                    p_type,
                    _flags,
                    p_offset,
                    _vaddr,
                    _paddr,
                    p_filesz,
                    _memsz,
                    _align,
                ) = ph

            segment_end = p_offset + p_filesz

            if segment_end > available:
                raise ValueError(
                    f"Segment {i} exceeds remaining firmware bytes"
                )

            spans.append(segment_end)

            if p_type == 1:  # PT_LOAD
                load_segments.append(
                    (p_offset, p_filesz, segment_end)
                )

            if p_type == 3 and p_filesz:  # PT_INTERP
                raw = data[
                    base + p_offset:
                    base + p_offset + p_filesz
                ]
                interpreters.append(
                    raw.split(b"\x00", 1)[0].decode(
                        "ascii", errors="replace"
                    )
                )

    sh_table_end = e_shoff + e_shnum * e_shentsize

    if e_shnum and e_shentsize:
        if e_shoff > available or sh_table_end > available:
            raise ValueError("Section-header table exceeds file bounds")

        spans.append(sh_table_end)

    span = max(spans)

    if span <= 0 or span > available:
        raise ValueError("Computed ELF size is outside file bounds")

    return {
        "base": base,
        "bits": bits,
        "endian": endian_name,
        "type": TYPE_NAMES.get(e_type, f"Unknown ({e_type})"),
        "machine": MACHINE_NAMES.get(
            e_machine, f"Unknown ({e_machine})"
        ),
        "entry": e_entry,
        "program_headers": e_phnum,
        "section_headers": e_shnum,
        "interpreter": interpreters,
        "load_segments": load_segments,
        "span": span,
    }


def main() -> None:
    if not FIRMWARE.is_file():
        raise SystemExit(f"Firmware not found: {FIRMWARE.resolve()}")

    data = FIRMWARE.read_bytes()
    OUTPUT.mkdir(parents=True, exist_ok=True)

    offsets = [
        match.start()
        for match in re.finditer(re.escape(b"\x7fELF"), data)
    ]

    report = [
        "EMBEDDED ELF ANALYSIS",
        "=" * 60,
        f"Firmware: {FIRMWARE.resolve()}",
        f"Size: {len(data):,} bytes",
        f"ELF signatures found: {len(offsets)}",
        "",
    ]

    for index, offset in enumerate(offsets, start=1):
        report.append(f"Candidate {index}: offset 0x{offset:X}")

        try:
            info = parse_elf(data, offset)
        except (ValueError, struct.error) as exc:
            report.append(f"  Rejected: {exc}")
            report.append("")
            continue

        report.extend([
            f"  Architecture: {info['bits']}-bit {info['machine']}",
            f"  Byte order: {info['endian']}",
            f"  ELF type: {info['type']}",
            f"  Entry point: 0x{info['entry']:X}",
            f"  Program headers: {info['program_headers']}",
            f"  Section headers: {info['section_headers']}",
            f"  Calculated file span: {info['span']:,} bytes",
        ])

        for interpreter in info["interpreter"]:
            report.append(f"  Interpreter: {interpreter}")

        for i, (segment_offset, file_size, end) in enumerate(
            info["load_segments"], start=1
        ):
            report.append(
                f"  LOAD {i}: offset=0x{segment_offset:X}, "
                f"size={file_size:,}, end=0x{end:X}"
            )

        span = info["span"]

        if span <= MAX_EXTRACT_SIZE:
            filename = f"elf_{offset:08X}.bin"
            target = OUTPUT / filename

            target.write_bytes(data[offset:offset + span])

            report.append(
                f"  Extracted: {target.resolve()}"
            )
        else:
            report.append(
                "  Not extracted: exceeds the 32 MiB safety limit"
            )

        report.append("")

    report_path = OUTPUT / "elf_report.txt"
    report_path.write_text(
        "\n".join(report) + "\n",
        encoding="utf-8",
    )

    print("\n".join(report))
    print(f"\nReport saved to: {report_path.resolve()}")


if __name__ == "__main__":
    main()