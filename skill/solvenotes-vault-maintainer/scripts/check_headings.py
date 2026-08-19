#!/usr/bin/env python3
"""Check heading hierarchy and duplicate anchors in long notes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter

from notes_utils import markdown_files, read_text, rel, strip_frontmatter

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def anchor(title: str) -> str:
    title = re.sub(r"\s+", " ", title.strip()).lower()
    return re.sub(r"[\\[\\]#^|]", "", title)


def visible_lines(text: str) -> list[str]:
    """Return frontmatter/code-masked lines while preserving line positions."""
    lines = strip_frontmatter(text).splitlines()
    visible: list[str] = []
    fence_char = ""
    fence_length = 0
    for line in lines:
        match = FENCE_RE.match(line)
        if fence_char:
            visible.append("<fenced-code>")
            if match and match.group(1)[0] == fence_char and len(match.group(1)) >= fence_length:
                fence_char = ""
                fence_length = 0
            continue
        if match:
            marker = match.group(1)
            fence_char = marker[0]
            fence_length = len(marker)
            visible.append("<fenced-code>")
            continue
        visible.append(line)
    return visible


def analyze_headings(text: str) -> tuple[list[tuple[int, str, int, int]], list[str]]:
    """Return parsed headings and structural issues for one Markdown document."""
    lines = visible_lines(text)
    headings: list[tuple[int, str, int, int]] = []
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if not match:
            continue
        headings.append((len(match.group(1)), match.group(2).strip(), index + 1, index))

    issues: list[str] = []
    for (prev_level, _, _, _), (level, title, line_no, _) in zip(headings, headings[1:]):
        if level - prev_level > 1:
            issues.append(f"{line_no}: heading jumps from H{prev_level} to H{level} ({title})")

    counts = Counter(anchor(title) for _, title, _, _ in headings)
    for level, title, line_no, _ in headings:
        if counts[anchor(title)] > 1 and level <= 2:
            issues.append(f"{line_no}: duplicate H{level} anchor ({title})")

    for heading_index, (level, title, line_no, body_start) in enumerate(headings):
        next_heading = headings[heading_index + 1] if heading_index + 1 < len(headings) else None
        if next_heading is not None and next_heading[0] > level:
            continue
        body_end = next_heading[3] if next_heading is not None else len(lines)
        if not any(line.strip() for line in lines[body_start + 1 : body_end]):
            issues.append(f"{line_no}: empty H{level} section ({title})")
    return headings, issues


def heading_issues_for_text(text: str) -> list[str]:
    """Expose heading checks for focused regression tests."""
    return analyze_headings(text)[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    issues: list[str] = []
    heading_count = 0
    for path in markdown_files():
        headings, file_issues = analyze_headings(read_text(path))
        heading_count += len(headings)
        issues.extend(f"{rel(path)}:{issue}" for issue in file_issues)

    payload = {"headings_checked": heading_count, "heading_issues": len(issues), "issues": issues[:100]}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"headings_checked {heading_count}")
        print(f"heading_issues {len(issues)}")
        for issue in issues[:100]:
            print(f"ISSUE {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
