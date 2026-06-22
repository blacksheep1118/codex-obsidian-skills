#!/usr/bin/env python3
"""Validate source-to-note coverage evidence for PPT/PDF course notes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
import unicodedata


SOURCE_EXTENSIONS = {".pdf", ".ppt", ".pptx"}
SOURCE_EXAMPLE_LABELS = ("源资料例题", "源课件例题")
GENERATED_MARKER = "生成：PPT/PDF 未提供独立可抽取例题"
SUPPLEMENT_HEADING = "## PPT/PDF 页级补充索引"
RESIDUAL_REVIEW_MARKERS = (
    "需复核",
    "人工确认",
    "人工打开",
    "手动打开",
    "打开课件确认",
    "open the slides manually",
)


@dataclass(frozen=True)
class CoverageIssue:
    kind: str
    path: Path
    message: str


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"\s+", " ", normalized)


def parse_mapping(value: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise argparse.ArgumentTypeError(f"invalid mapping item, expected source=notes: {item}")
        source, notes = item.split("=", 1)
        source = source.strip()
        notes = notes.strip()
        if not source or not notes:
            raise argparse.ArgumentTypeError(f"invalid mapping item, expected source=notes: {item}")
        mapping[source] = notes
    return mapping


def markdown_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if ".git" not in path.parts)


def source_files(source_root: Path) -> list[Path]:
    return sorted(
        path
        for path in source_root.rglob("*")
        if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS
    )


def course_text(notes_dir: Path) -> str:
    pieces: list[str] = []
    for name in ("source_manifest.md", "99_内容覆盖审查.md"):
        path = notes_dir / name
        if path.exists():
            pieces.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(pieces)


def check_source_mappings(source_root: Path, notes_root: Path, mapping: dict[str, str]) -> tuple[int, list[Path], list[CoverageIssue]]:
    issues: list[CoverageIssue] = []
    mapped_notes_dirs: list[Path] = []
    total = 0
    for source_name, notes_name in mapping.items():
        source_dir = source_root / source_name
        notes_dir = notes_root / notes_name
        if not source_dir.is_dir():
            issues.append(CoverageIssue("missing_source_dir", source_dir, "mapped source directory does not exist"))
            continue
        if not notes_dir.is_dir():
            issues.append(CoverageIssue("missing_notes_dir", notes_dir, "mapped notes directory does not exist"))
            continue
        mapped_notes_dirs.append(notes_dir)
        corpus = normalize_text(course_text(notes_dir))
        for path in source_files(source_dir):
            total += 1
            relative = str(path.relative_to(source_dir))
            candidates = (relative, path.name, path.stem)
            if not any(normalize_text(candidate) in corpus for candidate in candidates):
                issues.append(
                    CoverageIssue(
                        "missing_source_mapping",
                        path,
                        "source file name/stem is absent from source_manifest.md and 99_内容覆盖审查.md",
                    )
                )
    return total, mapped_notes_dirs, issues


def has_source_or_generated_example(line: str) -> bool:
    has_source_example = any(label in line for label in SOURCE_EXAMPLE_LABELS) and (
        "（/" in line or "来源：`" in line or "源资料：`" in line
    )
    has_generated_example = GENERATED_MARKER in line and "补充题（/" in line
    return has_source_example or has_generated_example


def check_example_evidence(notes_dirs: list[Path]) -> tuple[int, int, int, int, list[CoverageIssue]]:
    supplement_notes = 0
    supplement_bullets = 0
    source_example_lines = 0
    generated_lines = 0
    issues: list[CoverageIssue] = []

    for notes_dir in sorted({path.resolve() for path in notes_dirs}):
        local_source_examples = 0
        local_generated_lines = 0
        files = markdown_files(notes_dir)
        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            in_supplement = False
            if SUPPLEMENT_HEADING in text:
                supplement_notes += 1
            for line_number, line in enumerate(text.splitlines(), start=1):
                if line.startswith("## "):
                    in_supplement = line.strip() == SUPPLEMENT_HEADING
                    continue
                if in_supplement and line.startswith("- "):
                    supplement_bullets += 1
                    if "来源：`" not in line or "页/slide：" not in line or "主题：" not in line:
                        issues.append(CoverageIssue("bad_supplement_fields", path, f"line {line_number} lacks source/page/topic fields"))
                    if not has_source_or_generated_example(line):
                        issues.append(CoverageIssue("bad_supplement_example", path, f"line {line_number} lacks source example or generated-question evidence"))

                if any(label in line for label in SOURCE_EXAMPLE_LABELS):
                    source_example_lines += 1
                    local_source_examples += 1
                    if "（/" not in line and "源资料：`" not in line:
                        issues.append(CoverageIssue("bad_source_example", path, f"line {line_number} lacks a traceable source marker"))
                if "生成辅助题" in line or "补充题（/" in line:
                    generated_lines += 1
                    local_generated_lines += 1
                    if GENERATED_MARKER not in line and not any(label in line for label in SOURCE_EXAMPLE_LABELS):
                        issues.append(CoverageIssue("bad_generated_example", path, f"line {line_number} lacks generated-question source rationale"))
                if any(marker in line for marker in RESIDUAL_REVIEW_MARKERS):
                    issues.append(CoverageIssue("residual_manual_review_marker", path, f"line {line_number} still contains a manual-review marker"))
        if files and local_source_examples + local_generated_lines == 0:
            issues.append(CoverageIssue("no_example_evidence", notes_dir, "mapped notes directory has no source-derived or generated example evidence"))

    return supplement_notes, supplement_bullets, source_example_lines, generated_lines, issues


def main() -> int:
    configure_output_encoding()
    parser = argparse.ArgumentParser(description="Check PPT/PDF source coverage evidence in Obsidian notes.")
    parser.add_argument("--source-root", type=Path, required=True, help="Root directory containing PPT/PDF source folders")
    parser.add_argument("--notes-root", type=Path, required=True, help="Root directory containing Obsidian notes")
    parser.add_argument(
        "--mapping",
        type=parse_mapping,
        required=True,
        help="Comma-separated source=notes directory mapping, for example '课程源=课程笔记,raw=notes'",
    )
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    notes_root = args.notes_root.resolve()
    total_sources, mapped_notes_dirs, mapping_issues = check_source_mappings(source_root, notes_root, args.mapping)
    supplement_notes, supplement_bullets, source_examples, generated_lines, evidence_issues = check_example_evidence(mapped_notes_dirs)
    issues = mapping_issues + evidence_issues

    print(f"course_source_files {total_sources}")
    print(f"missing_source_mappings {len(mapping_issues)}")
    print(f"supplement_index_notes {supplement_notes}")
    print(f"supplement_bullets {supplement_bullets}")
    print(f"source_example_lines {source_examples}")
    print(f"generated_lines {generated_lines}")
    print(f"coverage_evidence_issues {len(issues)}")
    for issue in issues:
        try:
            display_path = issue.path.relative_to(notes_root)
        except ValueError:
            try:
                display_path = issue.path.relative_to(source_root)
            except ValueError:
                display_path = issue.path
        print(f"{issue.kind.upper()}: {display_path}: {issue.message}")

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
