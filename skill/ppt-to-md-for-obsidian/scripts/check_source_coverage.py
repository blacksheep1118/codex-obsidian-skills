#!/usr/bin/env python3
"""Validate source-to-note coverage evidence for PPT/PDF course notes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
import unicodedata
from typing import Optional


SOURCE_EXTENSIONS = {".pdf", ".ppt", ".pptx"}
SOURCE_EXAMPLE_LABELS = ("源资料例题", "源课件例题")
GENERATED_MARKER = "生成：PPT/PDF 未提供独立可抽取例题"
SUPPLEMENT_HEADING = "## PPT/PDF 页级补充索引"
SOURCE_REF_RE = re.compile(r"`([^`]+\.(?:pdf|pptx?|PDF|PPTX?))`")
WIKI_LINK_RE = re.compile(r"\[\[([^]|#]+)(?:#[^]|]+)?(?:\|[^\]]+)?\]\]")
CHAPTER_RE = re.compile(r"第\s*([零〇一二三四五六七八九十百\d]+)\s*[章节章]")
LECTURE_RE = re.compile(r"第\s*([零〇一二三四五六七八九十百\d]+)\s*[讲講]|lecture\s*0*(\d+[a-z]?)", re.I)
EVIDENCE_MARKERS = ("来源", "源资料", "源课件", "补充题", "页/slide")
LEGACY_FAILURE_LABELS = ("PPT不可读", "PDF不可读", "待人工确认", "待手工确认")
RESIDUAL_REVIEW_MARKERS = (
    "需复核",
    "人工确认",
    "人工打开",
    "手动打开",
    "打开课件确认",
    "open the slides manually",
)
CHINESE_NUMBERS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


@dataclass(frozen=True)
class CoverageIssue:
    kind: str
    path: Path
    message: str


@dataclass(frozen=True)
class SourceEntry:
    course_name: str
    path: Path
    course_relative: str
    root_relative: str
    name: str
    stem: str
    chapter_signature: Optional[str]


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"\s+", " ", normalized)


def normalize_path_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).replace("\\", "/").strip()


def chinese_number_to_int(value: str) -> Optional[int]:
    value = value.strip()
    if value.isdigit():
        return int(value)
    if value == "十":
        return 10
    if "十" in value:
        left, right = value.split("十", 1)
        tens = CHINESE_NUMBERS.get(left, 1) if left else 1
        ones = CHINESE_NUMBERS.get(right, 0) if right else 0
        return tens * 10 + ones
    return CHINESE_NUMBERS.get(value)


def extract_chapter_signature(text: str) -> Optional[str]:
    match = CHAPTER_RE.search(text)
    if match:
        number = chinese_number_to_int(match.group(1))
        if number is not None:
            return f"chapter:{number}"
    match = LECTURE_RE.search(text)
    if match:
        value = match.group(1) or match.group(2)
        if value:
            number = chinese_number_to_int(value)
            return f"lecture:{number if number is not None else value.lower()}"
    return None


def chapter_signatures_conflict(source_signature: Optional[str], target_signature: Optional[str]) -> bool:
    if not source_signature or not target_signature:
        return False
    if not source_signature.startswith("chapter:") or not target_signature.startswith("chapter:"):
        return False
    return source_signature != target_signature


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


def build_source_entries(source_root: Path, source_name: str) -> list[SourceEntry]:
    source_dir = source_root / source_name
    entries: list[SourceEntry] = []
    for path in source_files(source_dir):
        course_relative = path.relative_to(source_dir).as_posix()
        root_relative = path.relative_to(source_root).as_posix()
        signature_text = "\n".join((root_relative, course_relative, path.stem))
        entries.append(
            SourceEntry(
                course_name=source_name,
                path=path,
                course_relative=course_relative,
                root_relative=root_relative,
                name=path.name,
                stem=path.stem,
                chapter_signature=extract_chapter_signature(signature_text),
            )
        )
    return entries


def course_text(notes_dir: Path) -> str:
    pieces: list[str] = []
    for name in ("source_manifest.md", "99_内容覆盖审查.md"):
        path = notes_dir / name
        if path.exists():
            pieces.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(pieces)


def match_source_entries(ref: str, entries: list[SourceEntry]) -> list[SourceEntry]:
    ref_norm = normalize_path_text(ref)
    ref_text = normalize_text(ref_norm)
    matches: list[SourceEntry] = []
    for entry in entries:
        exact_candidates = {
            normalize_path_text(entry.root_relative),
            normalize_path_text(entry.course_relative),
            normalize_path_text(entry.name),
        }
        text_candidates = {normalize_text(candidate) for candidate in exact_candidates}
        if ref_norm in exact_candidates or ref_text in text_candidates:
            matches.append(entry)
    return matches


def check_source_mappings(
    source_root: Path, notes_root: Path, mapping: dict[str, str]
) -> tuple[int, list[Path], list[SourceEntry], list[CoverageIssue]]:
    issues: list[CoverageIssue] = []
    mapped_notes_dirs: list[Path] = []
    entries: list[SourceEntry] = []
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
        local_entries = build_source_entries(source_root, source_name)
        entries.extend(local_entries)
        corpus = normalize_text(course_text(notes_dir))
        for entry in local_entries:
            total += 1
            candidates = (entry.course_relative, entry.root_relative, entry.name, entry.stem)
            if not any(normalize_text(candidate) in corpus for candidate in candidates):
                issues.append(
                    CoverageIssue(
                        "missing_source_mapping",
                        entry.path,
                        "source file name/stem is absent from source_manifest.md and 99_内容覆盖审查.md",
                    )
                )
    return total, mapped_notes_dirs, entries, issues


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


def check_text_hygiene(notes_dirs: list[Path]) -> list[CoverageIssue]:
    issues: list[CoverageIssue] = []
    for notes_dir in sorted({path.resolve() for path in notes_dirs}):
        for path in markdown_files(notes_dir):
            text = path.read_text(encoding="utf-8", errors="replace")
            for line_number, line in enumerate(text.splitlines(), start=1):
                bad_controls = [
                    char
                    for char in line
                    if (ord(char) < 32 and char not in "\t") or ord(char) == 127
                ]
                if bad_controls:
                    issues.append(CoverageIssue("control_character", path, f"line {line_number} contains hidden control characters"))
                    break
                for label in LEGACY_FAILURE_LABELS:
                    if label in line:
                        issues.append(CoverageIssue("legacy_failure_label", path, f"line {line_number} still contains {label!r}"))
    return issues


def check_audit_source_tables(
    notes_dirs: list[Path], entries: list[SourceEntry], require_course_prefixed_refs: bool
) -> list[CoverageIssue]:
    issues: list[CoverageIssue] = []
    audit_names = ("source_manifest.md", "99_内容覆盖审查.md")
    for notes_dir in sorted({path.resolve() for path in notes_dirs}):
        for audit_name in audit_names:
            path = notes_dir / audit_name
            if not path.exists():
                continue
            for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                refs = SOURCE_REF_RE.findall(line)
                if not refs:
                    continue
                links = WIKI_LINK_RE.findall(line)
                for ref in refs:
                    matches = match_source_entries(ref, entries)
                    for entry in matches:
                        if require_course_prefixed_refs and entry.course_name not in ("", "."):
                            ref_norm = normalize_path_text(ref)
                            root_norm = normalize_path_text(entry.root_relative)
                            if ref_norm != root_norm:
                                issues.append(
                                    CoverageIssue(
                                        "noncanonical_source_ref",
                                        path,
                                        f"line {line_number} uses {ref!r}; prefer root-relative source path {entry.root_relative!r}",
                                    )
                                )
                        if not entry.chapter_signature:
                            continue
                        for link in links:
                            link_signature = extract_chapter_signature(link)
                            if chapter_signatures_conflict(entry.chapter_signature, link_signature):
                                issues.append(
                                    CoverageIssue(
                                        "chapter_mismatch_source_link",
                                        path,
                                        f"line {line_number} maps source {ref!r} to note {link!r} with conflicting chapter marker",
                                    )
                                )
    return issues


def note_heading(path: Path) -> str:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# "):
            return line
    return ""


def line_mentions_source(line: str, entry: SourceEntry) -> bool:
    line_norm = normalize_text(line)
    candidates = (entry.root_relative, entry.course_relative, entry.name)
    return any(normalize_text(candidate) in line_norm for candidate in candidates)


def check_note_source_ownership(notes_dirs: list[Path], entries: list[SourceEntry]) -> list[CoverageIssue]:
    issues: list[CoverageIssue] = []
    skip_names = {"source_manifest.md", "99_内容覆盖审查.md"}
    for notes_dir in sorted({path.resolve() for path in notes_dirs}):
        for path in markdown_files(notes_dir):
            if path.name in skip_names:
                continue
            note_signature = extract_chapter_signature(f"{path.stem}\n{note_heading(path)}")
            if not note_signature:
                continue
            for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
                if not any(marker in line for marker in EVIDENCE_MARKERS):
                    continue
                for entry in entries:
                    if not chapter_signatures_conflict(entry.chapter_signature, note_signature):
                        continue
                    if line_mentions_source(line, entry):
                        issues.append(
                            CoverageIssue(
                                "chapter_mismatch_note_source",
                                path,
                                f"line {line_number} cites {entry.root_relative!r} inside a note with a conflicting chapter marker",
                            )
                        )
    return issues


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
    parser.add_argument(
        "--require-course-prefixed-source-refs",
        action="store_true",
        help="Require source refs in source_manifest.md and 99_内容覆盖审查.md to use root-relative paths such as 课程/ch1.pdf",
    )
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    notes_root = args.notes_root.resolve()
    total_sources, mapped_notes_dirs, entries, mapping_issues = check_source_mappings(source_root, notes_root, args.mapping)
    supplement_notes, supplement_bullets, source_examples, generated_lines, evidence_issues = check_example_evidence(mapped_notes_dirs)
    hygiene_issues = check_text_hygiene(mapped_notes_dirs)
    audit_issues = check_audit_source_tables(mapped_notes_dirs, entries, args.require_course_prefixed_source_refs)
    ownership_issues = check_note_source_ownership(mapped_notes_dirs, entries)
    issues = mapping_issues + evidence_issues + hygiene_issues + audit_issues + ownership_issues

    print(f"course_source_files {total_sources}")
    print(f"missing_source_mappings {len(mapping_issues)}")
    print(f"supplement_index_notes {supplement_notes}")
    print(f"supplement_bullets {supplement_bullets}")
    print(f"source_example_lines {source_examples}")
    print(f"generated_lines {generated_lines}")
    print(f"text_hygiene_issues {len(hygiene_issues)}")
    print(f"source_table_issues {len(audit_issues)}")
    print(f"note_source_ownership_issues {len(ownership_issues)}")
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
