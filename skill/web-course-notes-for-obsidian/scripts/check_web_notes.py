#!/usr/bin/env python3
"""Validate finalized web-course note folders against their source manifest."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from urllib.parse import unquote


RESIDUE_RE = re.compile(r"(status:\s*scaffold|待补充|TODO|To complete)", re.I)
SKIPPED_RE = re.compile(r"\b(skipped|inaccessible)\b|不可访问|跳过")
URL_RE = re.compile(r"https?://[^\s)>\]]+|file://[^\s)>\]]+")
DIRECT_RESOURCE_KINDS = {"book", "book_pdf", "pdf", "slides", "transcript"}
READING_LIST_KINDS = {"book_or_chapter", "book", "book_pdf", "pdf"}


@dataclass(frozen=True)
class ManifestRow:
    section: str
    values: dict[str, str]


@dataclass(frozen=True)
class WebNoteIssue:
    kind: str
    path: Path
    message: str


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]

    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in stripped:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    cells.append("".join(current).strip())
    return cells


def is_separator_row(line: str) -> bool:
    return bool(re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", line))


def normalize_url(value: str) -> str:
    return unquote(value.strip().rstrip("/"))


def load_manifest_rows(manifest: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    section = ""
    headers: list[str] = []

    for raw_line in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            section = line.removeprefix("## ").strip()
            headers = []
            continue
        if not line.startswith("|") or is_separator_row(line):
            continue
        cells = split_table_row(line)
        if not headers:
            headers = cells
            continue
        if len(cells) != len(headers):
            continue
        rows.append(ManifestRow(section=section, values=dict(zip(headers, cells))))

    return rows


def markdown_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if ".git" not in path.parts)


def note_files(root: Path) -> list[Path]:
    return [path for path in markdown_files(root) if path.name != "source_manifest.md"]


def manifest_covers_source(rows: list[ManifestRow], source: str) -> bool:
    expected = normalize_url(source)
    page_rows = [row for row in rows if row.section == "Pages"]
    for row in page_rows:
        candidates = [
            row.values.get("Original Source", ""),
            row.values.get("URL", ""),
            row.values.get("Title", ""),
        ]
        if any(normalize_url(candidate) == expected for candidate in candidates):
            return True
    return False


def file_mentions_url(path: Path, url: str) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    return normalize_url(url) in normalize_url(text)


def explicit_skipped_or_inaccessible(path: Path, url: str) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    return normalize_url(url) in normalize_url(text) and bool(SKIPPED_RE.search(text))


def manifest_requires_per_link_notes(rows: list[ManifestRow]) -> bool:
    page_rows = [row for row in rows if row.section == "Pages"]
    resource_rows = [row for row in rows if row.section == "Learning Resources"]
    if len(resource_rows) <= 1:
        return False
    page_kinds = {row.values.get("Kind", "") for row in page_rows}
    return bool(page_kinds & READING_LIST_KINDS) or any("reading" in row.values.get("Kind", "") for row in page_rows)


def normalize_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def has_error_value(value: str) -> bool:
    normalized = normalize_cell(value)
    return normalized not in {"", "-", "none", "n/a", "ok"}


def inaccessible_resource(row: ManifestRow) -> bool:
    access = normalize_cell(row.values.get("Access", ""))
    status = normalize_cell(row.values.get("Status", ""))
    error = row.values.get("Error", "")
    state = f"{access} {status}"
    markers = ("inaccessible", "blocked", "paywalled", "skipped", "failed", "error")
    return any(marker in state for marker in markers) or has_error_value(error)


def validate_web_notes(root: Path, sources: list[str], *, per_link_notes: bool = False) -> list[WebNoteIssue]:
    issues: list[WebNoteIssue] = []
    manifest = root / "source_manifest.md"
    if not manifest.exists():
        return [WebNoteIssue("missing_manifest", Path("source_manifest.md"), "source_manifest.md is required")]

    rows = load_manifest_rows(manifest)
    for source in sources:
        if not manifest_covers_source(rows, source):
            issues.append(WebNoteIssue("missing_user_source", manifest.relative_to(root), f"manifest does not cover user source: {source}"))

    for path in note_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if RESIDUE_RE.search(line):
                issues.append(
                    WebNoteIssue(
                        "scaffold_residue",
                        path.relative_to(root),
                        f"line {line_number} contains scaffold or unfinished placeholder text",
                    )
                )

    require_per_link = per_link_notes or manifest_requires_per_link_notes(rows)
    if require_per_link:
        notes = note_files(root)
        for row in rows:
            if row.section != "Learning Resources":
                continue
            url = row.values.get("URL", "")
            if not url:
                continue
            if inaccessible_resource(row):
                continue
            if any(file_mentions_url(path, url) or explicit_skipped_or_inaccessible(path, url) for path in notes):
                continue
            issues.append(
                WebNoteIssue(
                    "missing_per_link_note",
                    manifest.relative_to(root),
                    f"learning resource has no corresponding note or skipped/inaccessible status: {url}",
                )
            )

    return issues


def main() -> int:
    configure_output_encoding()
    parser = argparse.ArgumentParser(description="Check finalized web-course notes against source_manifest.md.")
    parser.add_argument("root", type=Path, help="Collection directory containing source_manifest.md")
    parser.add_argument("--source", action="append", default=[], help="User-supplied source URL or local path; may be repeated")
    parser.add_argument("--per-link-notes", action="store_true", help="Require every learning resource to have a note or explicit skipped/inaccessible status")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.exists():
        parser.error(f"directory does not exist: {root}")
    if not root.is_dir():
        parser.error(f"root must be a directory: {root}")

    issues = validate_web_notes(root, args.source, per_link_notes=args.per_link_notes)
    print(f"web_note_issues {len(issues)}")
    for issue in issues:
        print(f"{issue.kind.upper()}: {issue.path}: {issue.message}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
