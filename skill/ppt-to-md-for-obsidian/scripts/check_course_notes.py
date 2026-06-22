#!/usr/bin/env python3
"""Validate expected course-note outputs for the PPT-to-Obsidian workflow."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


OVERVIEW_NAMES = ("00_课程总览.md", "00_学习地图.md")
DETAIL_REVIEW = "知识点详细版_含公式.md"
CONCISE_REVIEW = "知识点精简复习版_含公式.md"
DETAIL_REVIEW_RE = re.compile(r"^(?:.+)?知识点详细版_含公式\.md$")
CONCISE_REVIEW_RE = re.compile(r"^(?:.+)?知识点精简复习版_含公式\.md$")
TEMPLATE_RE = re.compile(r"(相关知识链接|TODO|FIXME|TBD|待补|待完善)")
STRICT_TEMPLATE_RE = re.compile(r"(例题模板|高频答题模板|答题模板|空话|套话|占位|\.\.\.)")
EXAM_REVIEW_RE = re.compile(r"(考试复习|复习笔记)")
CHAPTER_NOTE_RE = re.compile(r"^(?!00_|99_)\d{2}_.+\.md$")
COVERAGE_AUDIT_RE = re.compile(r"(覆盖审查|coverage)", re.IGNORECASE)
SOURCE_MANIFEST_RE = re.compile(r"(source[_-]?manifest|源材料|source.*manifest)", re.IGNORECASE)


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class CourseNoteIssue:
    path: Path
    kind: str
    message: str


def count_unescaped_pipes(line: str) -> int:
    count = 0
    escaped = False
    for char in line:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "|":
            count += 1
    return count


TABLE_SEPARATOR_RE = re.compile(r"^\s*\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|\s*$")


def relative_issue(root: Path, path: Path, kind: str, message: str) -> CourseNoteIssue:
    return CourseNoteIssue(path.relative_to(root), kind, message)


def markdown_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if ".git" not in path.parts)


def find_overview(root: Path) -> Path | None:
    for name in OVERVIEW_NAMES:
        path = root / name
        if path.exists():
            return path
    for pattern in ("00_*课程总览.md", "00_*学习地图.md", "00_*总览.md"):
        matches = sorted(root.glob(pattern))
        if matches:
            return matches[0]
    return None


def count_nonblank_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def is_exam_review(path: Path) -> bool:
    return bool(EXAM_REVIEW_RE.search(path.stem))


def find_review_pair(root: Path) -> tuple[Path | None, Path | None]:
    exact_detail = root / DETAIL_REVIEW
    exact_concise = root / CONCISE_REVIEW
    detail = exact_detail if exact_detail.exists() else None
    concise = exact_concise if exact_concise.exists() else None

    if detail is None:
        detail_matches = sorted(path for path in root.glob("*.md") if DETAIL_REVIEW_RE.match(path.name))
        detail = detail_matches[0] if detail_matches else None
    if concise is None:
        concise_matches = sorted(path for path in root.glob("*.md") if CONCISE_REVIEW_RE.match(path.name))
        concise = concise_matches[0] if concise_matches else None

    return detail, concise


def is_detailed_review(path: Path, detail_review: Path | None) -> bool:
    return detail_review is not None and path == detail_review


def is_review_page(path: Path, detail_review: Path | None, concise_review: Path | None) -> bool:
    return path in {review for review in (detail_review, concise_review) if review is not None}


def is_conflict_marker(line: str, has_conflict_edges: bool) -> bool:
    stripped = line.strip()
    return stripped.startswith("<<<<<<<") or stripped.startswith(">>>>>>>") or (has_conflict_edges and stripped == "=======")


def find_table_issues(root: Path, path: Path, text: str) -> list[CourseNoteIssue]:
    issues: list[CourseNoteIssue] = []
    in_table = False
    expected_columns: int | None = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("|") and line.rstrip().endswith("|"):
            columns = count_unescaped_pipes(line) - 1
            if TABLE_SEPARATOR_RE.match(line):
                if expected_columns is None:
                    expected_columns = columns
                elif columns != expected_columns:
                    issues.append(
                        relative_issue(
                            root,
                            path,
                            "broken_table",
                            f"line {line_number} has {columns} columns, expected {expected_columns}",
                        )
                    )
                in_table = True
                continue

            if not in_table:
                expected_columns = columns
                in_table = True
            elif expected_columns is not None and columns != expected_columns:
                issues.append(
                    relative_issue(
                        root,
                        path,
                        "broken_table",
                        f"line {line_number} has {columns} columns, expected {expected_columns}; escape literal | as \\| or avoid wiki-link aliases inside tables",
                    )
                )
        else:
            in_table = False
            expected_columns = None
    return issues


def find_course_note_issues(
    root: Path,
    *,
    strict_depth: bool = False,
    allow_exam_review: bool = False,
    require_coverage_audit: bool = False,
    min_chapter_lines: int = 80,
    min_detailed_lines: int = 250,
    min_exam_review_lines: int = 250,
) -> list[CourseNoteIssue]:
    issues: list[CourseNoteIssue] = []
    files = markdown_files(root)

    overview = find_overview(root)
    if overview is None:
        issues.append(CourseNoteIssue(Path("."), "missing_overview", "expected 00_课程总览.md, 00_学习地图.md, or a local 00_*总览.md / 00_*学习地图.md variant"))

    detail_review, concise_review = find_review_pair(root)
    exam_review_paths = [path for path in files if is_exam_review(path)]
    if detail_review is not None and concise_review is not None:
        review_targets = [detail_review, concise_review]
    elif allow_exam_review and exam_review_paths:
        review_targets = exam_review_paths
    else:
        review_targets = [root / DETAIL_REVIEW, root / CONCISE_REVIEW]
        if detail_review is None:
            issues.append(relative_issue(root, root / DETAIL_REVIEW, "missing_review_page", "expected detailed review page is missing"))
        if concise_review is None:
            issues.append(relative_issue(root, root / CONCISE_REVIEW, "missing_review_page", "expected concise review page is missing"))

    if require_coverage_audit:
        if not any(COVERAGE_AUDIT_RE.search(path.name) for path in files):
            issues.append(CourseNoteIssue(Path("."), "missing_coverage_audit", "expected a source/content coverage audit note"))
        if not any(SOURCE_MANIFEST_RE.search(path.name) for path in files):
            issues.append(CourseNoteIssue(Path("."), "missing_source_manifest", "expected a source manifest note"))

    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        has_conflict_edges = "<<<<<<<" in text and ">>>>>>>" in text
        if not text.strip():
            issues.append(relative_issue(root, path, "empty_file", "Markdown file has no content"))
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            if is_conflict_marker(line, has_conflict_edges):
                issues.append(relative_issue(root, path, "conflict_marker", f"line {line_number} contains merge conflict marker"))
            if TEMPLATE_RE.search(line):
                issues.append(relative_issue(root, path, "template_residue", f"line {line_number} contains leftover template text"))
            if strict_depth and STRICT_TEMPLATE_RE.search(line):
                issues.append(relative_issue(root, path, "generic_template_residue", f"line {line_number} contains generic/template wording"))

        if sum(1 for line in text.splitlines() if line.strip().startswith("```")) % 2:
            issues.append(relative_issue(root, path, "unbalanced_fence", "odd number of fenced code block delimiters"))
        if text.count("$$") % 2:
            issues.append(relative_issue(root, path, "unbalanced_math", "odd number of block math delimiters"))
        issues.extend(find_table_issues(root, path, text))

        if strict_depth:
            nonblank_lines = count_nonblank_lines(text)
            if is_detailed_review(path, detail_review) and nonblank_lines < min_detailed_lines:
                issues.append(relative_issue(root, path, "thin_detailed_review", f"detailed review has {nonblank_lines} nonblank lines, expected at least {min_detailed_lines}"))
            elif is_exam_review(path) and nonblank_lines < min_exam_review_lines:
                issues.append(relative_issue(root, path, "thin_exam_review", f"exam review has {nonblank_lines} nonblank lines, expected at least {min_exam_review_lines}"))
            elif CHAPTER_NOTE_RE.match(path.name) and not is_review_page(path, detail_review, concise_review) and not is_exam_review(path):
                if nonblank_lines < min_chapter_lines:
                    issues.append(relative_issue(root, path, "thin_chapter_note", f"chapter note has {nonblank_lines} nonblank lines, expected at least {min_chapter_lines}"))

    if overview is not None:
        overview_text = overview.read_text(encoding="utf-8", errors="replace")
        for target in review_targets:
            if target.stem not in overview_text:
                issues.append(relative_issue(root, overview, "missing_review_link", f"overview should link {target.name}"))

    return issues


def main() -> int:
    configure_output_encoding()
    parser = argparse.ArgumentParser(description="Check PPT-to-Obsidian course-note outputs.")
    parser.add_argument("--strict-depth", action="store_true", help="also flag shallow notes and generic review wording")
    parser.add_argument("--allow-exam-review", action="store_true", help="allow one or more 考试复习/复习笔记 files instead of the two default review pages")
    parser.add_argument("--require-coverage-audit", action="store_true", help="require source manifest and coverage audit notes")
    parser.add_argument("--min-chapter-lines", type=int, default=80, help="minimum nonblank lines for numbered chapter notes in strict mode")
    parser.add_argument("--min-detailed-lines", type=int, default=250, help="minimum nonblank lines for the detailed review in strict mode")
    parser.add_argument("--min-exam-review-lines", type=int, default=250, help="minimum nonblank lines for exam review files in strict mode")
    parser.add_argument("root", type=Path, help="Course notes directory")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.exists():
        parser.error(f"directory does not exist: {root}")
    if not root.is_dir():
        parser.error(f"root must be a directory: {root}")

    issues = find_course_note_issues(
        root,
        strict_depth=args.strict_depth,
        allow_exam_review=args.allow_exam_review,
        require_coverage_audit=args.require_coverage_audit,
        min_chapter_lines=args.min_chapter_lines,
        min_detailed_lines=args.min_detailed_lines,
        min_exam_review_lines=args.min_exam_review_lines,
    )
    print(f"course_note_issues {len(issues)}")
    for issue in issues:
        print(f"{issue.kind.upper()}: {issue.path}: {issue.message}")

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
