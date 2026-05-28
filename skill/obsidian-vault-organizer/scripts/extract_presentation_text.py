#!/usr/bin/env python3
"""Extract readable text from PPTX and legacy PPT files for source audits."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import struct
import sys
import zipfile
from xml.etree import ElementTree as ET


END_OF_CHAIN = -2
FREE_SECTOR = -1
NO_STREAM = -1

PLACEHOLDER_RE = re.compile(
    r"^(?:"
    r"\d+|"
    r"幻灯片\s*\d+|"
    r"单击此处编辑.*|"
    r"Click to edit.*|"
    r"Microsoft PowerPoint.*"
    r")$",
    re.I,
)


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = sum(1 for char in text if char.isprintable() or char in "\r\n\t")
    return printable / len(text)


def clean_line(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\x00", "")).strip()


def is_useful_line(text: str) -> bool:
    line = clean_line(text)
    if not line or PLACEHOLDER_RE.match(line):
        return False
    return any(char.isalnum() or "\u4e00" <= char <= "\u9fff" for char in line)


def cfb_sector_offset(sector_id: int, sector_size: int) -> int:
    return 512 + sector_id * sector_size


def read_cfb_stream(path: Path, stream_name: str) -> bytes:
    data = path.read_bytes()
    if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise ValueError(f"not a Compound File Binary document: {path}")

    sector_size = 1 << struct.unpack_from("<H", data, 30)[0]
    mini_sector_size = 1 << struct.unpack_from("<H", data, 32)[0]
    fat_sector_count = struct.unpack_from("<I", data, 44)[0]
    directory_start = struct.unpack_from("<i", data, 48)[0]
    mini_stream_cutoff = struct.unpack_from("<I", data, 56)[0]
    mini_fat_start = struct.unpack_from("<i", data, 60)[0]
    mini_fat_sector_count = struct.unpack_from("<I", data, 64)[0]
    difat_start = struct.unpack_from("<i", data, 68)[0]
    difat_sector_count = struct.unpack_from("<I", data, 72)[0]

    difat = list(struct.unpack_from("<109i", data, 76))
    current = difat_start
    seen: set[int] = set()
    while current not in (END_OF_CHAIN, FREE_SECTOR, NO_STREAM) and current not in seen:
        seen.add(current)
        offset = cfb_sector_offset(current, sector_size)
        entries = list(struct.unpack_from(f"<{sector_size // 4}i", data, offset))
        difat.extend(entries[:-1])
        current = entries[-1]
        if len(seen) >= difat_sector_count:
            break

    fat_sectors = [sector for sector in difat if sector >= 0][:fat_sector_count]
    fat: list[int] = []
    for sector in fat_sectors:
        offset = cfb_sector_offset(sector, sector_size)
        fat.extend(struct.unpack_from(f"<{sector_size // 4}i", data, offset))

    def read_chain(start_sector: int) -> bytes:
        output = bytearray()
        sector = start_sector
        chain_seen: set[int] = set()
        while sector >= 0 and sector not in chain_seen:
            chain_seen.add(sector)
            offset = cfb_sector_offset(sector, sector_size)
            output.extend(data[offset : offset + sector_size])
            if sector >= len(fat):
                break
            sector = fat[sector]
            if sector == END_OF_CHAIN:
                break
        return bytes(output)

    directory_data = read_chain(directory_start)
    entries: list[dict[str, int | str]] = []
    root_entry: dict[str, int | str] | None = None
    target_entry: dict[str, int | str] | None = None

    for offset in range(0, len(directory_data), 128):
        entry = directory_data[offset : offset + 128]
        if len(entry) < 128:
            continue
        name_length = struct.unpack_from("<H", entry, 64)[0]
        if name_length < 2:
            continue
        name = entry[: name_length - 2].decode("utf-16le", errors="ignore")
        entry_type = entry[66]
        start_sector = struct.unpack_from("<i", entry, 116)[0]
        size = struct.unpack_from("<Q", entry, 120)[0]
        item = {
            "name": name,
            "type": entry_type,
            "start": start_sector,
            "size": size,
        }
        entries.append(item)
        if entry_type == 5:
            root_entry = item
        if name == stream_name:
            target_entry = item

    if target_entry is None:
        raise KeyError(f"stream not found: {stream_name}")

    start = int(target_entry["start"])
    size = int(target_entry["size"])
    if size < mini_stream_cutoff and root_entry is not None:
        mini_fat = read_chain(mini_fat_start)[: mini_fat_sector_count * sector_size]
        mini_entries = list(struct.unpack_from(f"<{len(mini_fat) // 4}i", mini_fat, 0)) if mini_fat else []
        root_stream = read_chain(int(root_entry["start"]))[: int(root_entry["size"])]
        output = bytearray()
        mini_sector = start
        chain_seen: set[int] = set()
        while mini_sector >= 0 and mini_sector not in chain_seen:
            chain_seen.add(mini_sector)
            offset = mini_sector * mini_sector_size
            output.extend(root_stream[offset : offset + mini_sector_size])
            if mini_sector >= len(mini_entries):
                break
            mini_sector = mini_entries[mini_sector]
            if mini_sector == END_OF_CHAIN:
                break
        return bytes(output[:size])

    return read_chain(start)[:size]


def parse_ppt_records(payload: bytes, output: list[str]) -> None:
    position = 0
    payload_length = len(payload)
    while position + 8 <= payload_length:
        instance_version, record_type, record_length = struct.unpack_from("<HHI", payload, position)
        version = instance_version & 0xF
        start = position + 8
        end = start + record_length
        if end > payload_length:
            break
        body = payload[start:end]

        if record_type in (4000, 4026):
            text = body.decode("utf-16le", errors="ignore")
            if printable_ratio(text) > 0.65:
                for line in text.splitlines():
                    if is_useful_line(line):
                        output.append(clean_line(line))
        elif record_type == 4008:
            for encoding in ("gbk", "cp1252", "utf-8"):
                text = body.decode(encoding, errors="ignore")
                if printable_ratio(text) > 0.65:
                    for line in text.splitlines():
                        if is_useful_line(line):
                            output.append(clean_line(line))
                    break

        if version == 0xF and record_length:
            parse_ppt_records(body, output)
        position = end


def extract_ppt(path: Path) -> str:
    stream = read_cfb_stream(path, "PowerPoint Document")
    lines: list[str] = []
    parse_ppt_records(stream, lines)
    return join_deduped(lines)


def slide_number(path: str) -> tuple[int, str]:
    match = re.search(r"slide(\d+)\.xml$", path)
    return (int(match.group(1)) if match else 0, path)


def extract_text_from_xml(xml_data: bytes) -> list[str]:
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return []
    lines: list[str] = []
    for node in root.iter():
        if node.tag.endswith("}t") and node.text and is_useful_line(node.text):
            lines.append(clean_line(node.text))
    return lines


def extract_pptx(path: Path) -> str:
    sections: list[str] = []
    with zipfile.ZipFile(path) as archive:
        slide_names = sorted(
            (name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")),
            key=slide_number,
        )
        for index, name in enumerate(slide_names, start=1):
            lines = extract_text_from_xml(archive.read(name))
            if lines:
                sections.append(f"--- Slide {index} ---")
                sections.extend(lines)
    return join_deduped(sections)


def join_deduped(lines: list[str]) -> str:
    output: list[str] = []
    previous = ""
    for line in lines:
        cleaned = clean_line(line)
        if not cleaned or cleaned == previous:
            continue
        output.append(cleaned)
        previous = cleaned
    return "\n".join(output).strip() + "\n"


def extract(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pptx":
        return extract_pptx(path)
    if suffix == ".ppt":
        return extract_ppt(path)
    raise ValueError(f"unsupported presentation extension: {path.suffix}")


def output_path_for(source: Path, output_dir: Path) -> Path:
    stem = re.sub(r"[\s/]+", "_", source.stem).strip("_")
    return output_dir / f"{stem}.txt"


def main() -> int:
    configure_output_encoding()
    parser = argparse.ArgumentParser(description="Extract text from PPTX and legacy PPT files.")
    parser.add_argument("sources", nargs="+", type=Path, help="PPT or PPTX files")
    parser.add_argument("--output-dir", type=Path, help="write one .txt file per source")
    args = parser.parse_args()

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    exit_code = 0
    for source in args.sources:
        try:
            text = extract(source)
        except Exception as exc:
            print(f"ERROR: {source}: {exc}", file=sys.stderr)
            exit_code = 1
            continue

        if args.output_dir:
            target = output_path_for(source, args.output_dir)
            target.write_text(text, encoding="utf-8")
            print(f"wrote {target}")
        else:
            print(f"===== {source} =====")
            print(text, end="")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
