#!/usr/bin/env python3
"""Validate expected course-note outputs for the PPT-to-Obsidian workflow."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re


OVERVIEW_NAMES = ("00_课程总览.md", "00_学习地图.md")
DETAIL_REVIEW = "知识点详细版_含公式.md"
CONCISE_REVIEW = "知识点精简复习版_含公式.md"
TEMPLATE_RE = re.compile(r"(相关知识链接|TODO|FIXME|TBD|待补|待完善)")


@dataclass(frozen=True)
class CourseNoteIssue:
    path: Path
    kind: str
    message: str


def relative_issue(root: Path, path: Path, kind: str, message: str) -> CourseNoteIssue:
    return CourseNoteIssue(path.relative_to(root), kind, message)


def markdown_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if ".git" not in path.parts)


def is_conflict_marker(line: str, has_conflict_edges: bool) -> bool:
    stripped = line.strip()
    return stripped.startswith("<<<<<<<") or stripped.startswith(">>>>>>>") or (has_conflict_edges and stripped == "=======")


def find_course_note_issues(root: Path) -> list[CourseNoteIssue]:
    issues: list[CourseNoteIssue] = []
    files = markdown_files(root)

    overview = next((root / name for name in OVERVIEW_NAMES if (root / name).exists()), None)
    if overview is None:
        issues.append(CourseNoteIssue(Path("."), "missing_overview", "expected 00_课程总览.md or 00_学习地图.md"))

    for required in (DETAIL_REVIEW, CONCISE_REVIEW):
        if not (root / required).exists():
            issues.append(CourseNoteIssue(Path(required), "missing_review_page", "expected review page is missing"))

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

        if sum(1 for line in text.splitlines() if line.strip().startswith("```")) % 2:
            issues.append(relative_issue(root, path, "unbalanced_fence", "odd number of fenced code block delimiters"))
        if text.count("$$") % 2:
            issues.append(relative_issue(root, path, "unbalanced_math", "odd number of block math delimiters"))

    if overview is not None:
        overview_text = overview.read_text(encoding="utf-8", errors="replace")
        for required in (DETAIL_REVIEW, CONCISE_REVIEW):
            if Path(required).stem not in overview_text:
                issues.append(relative_issue(root, overview, "missing_review_link", f"overview should link {required}"))

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Check PPT-to-Obsidian course-note outputs.")
    parser.add_argument("root", type=Path, help="Course notes directory")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.exists():
        parser.error(f"directory does not exist: {root}")
    if not root.is_dir():
        parser.error(f"root must be a directory: {root}")

    issues = find_course_note_issues(root)
    print(f"course_note_issues {len(issues)}")
    for issue in issues:
        print(f"{issue.kind.upper()}: {issue.path}: {issue.message}")

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
