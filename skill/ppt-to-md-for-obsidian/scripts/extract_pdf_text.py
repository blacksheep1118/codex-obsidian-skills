#!/usr/bin/env python3
"""Extract PDF text into Markdown.

Uses pypdf by default and falls back to pdfplumber or the pdftotext CLI when
available. The output is raw source material for note rewriting.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys


MIN_TEXT_CHARS_PER_PAGE = 20
LOW_COVERAGE_WARNING = "Warning: low text coverage; source may be scanned/image-only and needs OCR or manual inspection."


class PdfExtractionError(RuntimeError):
    """Raised when no PDF text extraction backend can provide page data."""


@dataclass(frozen=True)
class PdfBackendResult:
    name: str
    pages: list[str]
    error: str | None = None

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def text_char_count(self) -> int:
        return sum(len(page.strip()) for page in self.pages)

    @property
    def empty_page_count(self) -> int:
        return sum(1 for page in self.pages if not page.strip())

    @property
    def nonempty_page_count(self) -> int:
        return self.page_count - self.empty_page_count


@dataclass(frozen=True)
class PdfExtractionResult:
    markdown: str
    backend: str
    low_coverage: bool
    empty_pages: int
    char_count: int
    page_count: int


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


def extract_with_pdftotext(path: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    pages = result.stdout.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return [page.strip("\n") for page in pages]


def low_text_coverage(result: PdfBackendResult) -> bool:
    if not result.pages:
        return True
    if result.text_char_count == 0:
        return True
    return result.text_char_count < result.page_count * MIN_TEXT_CHARS_PER_PAGE


def backend_sort_key(result: PdfBackendResult) -> tuple[int, int, int]:
    return (result.nonempty_page_count, result.text_char_count, result.page_count)


def choose_backend(path: Path) -> PdfBackendResult:
    backends = [
        ("pypdf", extract_with_pypdf),
        ("pdfplumber", extract_with_pdfplumber),
        ("pdftotext", extract_with_pdftotext),
    ]
    attempted: list[PdfBackendResult] = []
    best: PdfBackendResult | None = None

    for name, extractor in backends:
        try:
            pages = extractor(path)
            result = PdfBackendResult(name=name, pages=pages)
        except Exception as exc:
            result = PdfBackendResult(name=name, pages=[], error=str(exc))
        attempted.append(result)

        if result.pages and (best is None or backend_sort_key(result) > backend_sort_key(best)):
            best = result
        if result.pages and not low_text_coverage(result):
            return result

    if best is not None:
        return best

    details = "; ".join(f"{result.name}: {result.error or 'no pages'}" for result in attempted)
    raise PdfExtractionError(
        "Missing dependency or no readable pages: install pypdf, pdfplumber, or pdftotext to extract PDF text."
        f" Attempts: {details}"
    )


def render_markdown(path: Path, result: PdfBackendResult, *, low_coverage: bool) -> str:
    out = [f"# Extracted PDF Text: {path.name}", ""]
    if low_coverage:
        out.extend([LOW_COVERAGE_WARNING, ""])
    out.extend(
        [
            f"- Backend: `{result.name}`",
            f"- Pages: {result.page_count}",
            f"- Empty text pages: {result.empty_page_count}",
            f"- Text characters: {result.text_char_count}",
            f"- Low coverage: {str(low_coverage).lower()}",
            "",
        ]
    )
    for idx, text in enumerate(result.pages, start=1):
        out.append(f"## Page {idx}")
        out.append("")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            out.extend(lines)
        else:
            out.append("[No extractable text]")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def extract_pdf_result(path: Path) -> PdfExtractionResult:
    result = choose_backend(path)
    is_low_coverage = low_text_coverage(result)
    return PdfExtractionResult(
        markdown=render_markdown(path, result, low_coverage=is_low_coverage),
        backend=result.name,
        low_coverage=is_low_coverage,
        empty_pages=result.empty_page_count,
        char_count=result.text_char_count,
        page_count=result.page_count,
    )


def extract_pdf(path: Path) -> str:
    return extract_pdf_result(path).markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract PDF text into Markdown.")
    parser.add_argument("pdf", type=Path, help="Path to a .pdf file")
    parser.add_argument("--out", type=Path, help="Output Markdown path")
    args = parser.parse_args()

    if not args.pdf.exists():
        parser.error(f"file does not exist: {args.pdf}")
    if args.pdf.suffix.lower() != ".pdf":
        parser.error("input must be a .pdf file")

    try:
        md = extract_pdf(args.pdf)
    except PdfExtractionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.out:
        args.out.write_text(md, encoding="utf-8")
    else:
        print(md, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
