#!/usr/bin/env python3
"""Extract PDF text into Markdown.

Uses pypdf by default and falls back to pdfplumber when installed. The output
is raw source material for note rewriting.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def extract_with_pypdf(path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return []

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return pages


def extract_with_pdfplumber(path: Path) -> list[str]:
    try:
        import pdfplumber
    except ImportError:
        return []

    pages = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return pages


def extract_pdf(path: Path) -> str:
    pages = extract_with_pypdf(path)
    if not pages:
        pages = extract_with_pdfplumber(path)
    if not pages:
        sys.exit("Missing dependency: install pypdf or pdfplumber to extract PDF text.")

    out = [f"# Extracted PDF Text: {path.name}", ""]
    for idx, text in enumerate(pages, start=1):
        out.append(f"## Page {idx}")
        out.append("")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            out.extend(lines)
        else:
            out.append("[No extractable text]")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract PDF text into Markdown.")
    parser.add_argument("pdf", type=Path, help="Path to a .pdf file")
    parser.add_argument("--out", type=Path, help="Output Markdown path")
    args = parser.parse_args()

    if not args.pdf.exists():
        parser.error(f"file does not exist: {args.pdf}")
    if args.pdf.suffix.lower() != ".pdf":
        parser.error("input must be a .pdf file")

    md = extract_pdf(args.pdf)
    if args.out:
        args.out.write_text(md, encoding="utf-8")
    else:
        print(md, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
