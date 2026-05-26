#!/usr/bin/env python3
"""Extract ordered text from a PPTX file into Markdown.

This script is intentionally conservative: it extracts visible text, table
cells, and speaker notes when python-pptx exposes them. The output is raw
material for rewriting, not final Obsidian notes.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys


@dataclass
class ShapeRecord:
    top: int
    left: int
    text: str
    kind: str = "text"


def position(shape) -> tuple[int, int]:
    top = int(getattr(shape, "top", 0) or 0)
    left = int(getattr(shape, "left", 0) or 0)
    return top, left


def iter_shape_text(shape):
    if getattr(shape, "has_text_frame", False) and shape.text:
        yield shape.text

    if getattr(shape, "has_table", False):
        table = shape.table
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                yield " | ".join(cells)

    if getattr(shape, "shapes", None):
        for subshape in shape.shapes:
            yield from iter_shape_text(subshape)


def iter_shape_records(shape, include_media_placeholders: bool = True):
    top, left = position(shape)
    emitted_text = False
    for text in iter_shape_text(shape):
        text = text.strip()
        if text:
            emitted_text = True
            yield ShapeRecord(top=top, left=left, text=text, kind="text")

    if emitted_text or not include_media_placeholders:
        return

    shape_type = str(getattr(shape, "shape_type", "")).lower()
    name = getattr(shape, "name", "")
    if "picture" in shape_type:
        yield ShapeRecord(top=top, left=left, text=f"[Image placeholder: {name or 'picture'}]", kind="image")
    elif getattr(shape, "has_chart", False):
        yield ShapeRecord(top=top, left=left, text=f"[Chart placeholder: {name or 'chart'}]", kind="chart")


def extract_notes(slide):
    try:
        notes_slide = getattr(slide, "notes_slide", None)
    except Exception:
        notes_slide = None
    if notes_slide is None:
        return []
    chunks = []
    for shape in notes_slide.shapes:
        if getattr(shape, "has_text_frame", False) and shape.text:
            text = shape.text.strip()
            if text and text.lower() != "click to add notes":
                chunks.append(text)
    return chunks


def slide_title(records: list[ShapeRecord]) -> str | None:
    for record in records:
        if record.kind != "text":
            continue
        for line in record.text.splitlines():
            line = line.strip()
            if line:
                return line
    return None


def extract_pptx(path: Path, include_media_placeholders: bool = True, include_slide_title: bool = True) -> str:
    try:
        from pptx import Presentation
    except ImportError:
        sys.exit(
            "Missing dependency: python-pptx. Install it with "
            "`python -m pip install python-pptx` in the active environment."
        )

    prs = Presentation(str(path))
    out = [f"# Extracted PPTX Text: {path.name}", ""]

    for idx, slide in enumerate(prs.slides, start=1):
        records = []
        seen = set()
        for shape in slide.shapes:
            for record in iter_shape_records(shape, include_media_placeholders=include_media_placeholders):
                key = (record.text, record.top, record.left)
                if key not in seen:
                    records.append(record)
                    seen.add(key)
        records.sort(key=lambda record: (record.top, record.left))

        title = slide_title(records) if include_slide_title else None
        if title:
            out.append(f"## Slide {idx}: {title}")
        else:
            out.append(f"## Slide {idx}")
        out.append("")

        if records:
            for record in records:
                chunk = record.text
                for line in chunk.splitlines():
                    line = line.strip()
                    if line:
                        out.append(f"- {line}")
        else:
            out.append("- [No visible text extracted]")

        notes = extract_notes(slide)
        if notes:
            out.append("")
            out.append("### Speaker Notes")
            for note in notes:
                for line in note.splitlines():
                    line = line.strip()
                    if line:
                        out.append(f"- {line}")

        out.append("")

    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract PPTX text into Markdown.")
    parser.add_argument("pptx", type=Path, help="Path to a .pptx file")
    parser.add_argument("--out", type=Path, help="Output Markdown path")
    parser.add_argument("--no-media-placeholders", action="store_true", help="Do not emit image/chart placeholders.")
    parser.add_argument("--no-slide-title", action="store_true", help="Do not add detected slide titles to headings.")
    args = parser.parse_args()

    if not args.pptx.exists():
        parser.error(f"file does not exist: {args.pptx}")
    if args.pptx.suffix.lower() != ".pptx":
        parser.error("input must be a .pptx file")

    md = extract_pptx(
        args.pptx,
        include_media_placeholders=not args.no_media_placeholders,
        include_slide_title=not args.no_slide_title,
    )
    if args.out:
        args.out.write_text(md, encoding="utf-8")
    else:
        print(md, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
