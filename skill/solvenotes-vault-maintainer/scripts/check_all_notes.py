#!/usr/bin/env python3
"""Run core vault checks for every Markdown file."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

from notes_utils import (
    ROOT,
    build_note_index,
    infer_note_type,
    markdown_files,
    read_text,
    rel,
    strip_frontmatter,
    text_without_code,
    wikilink_matches,
    wikilinks,
)

RESIDUE_RE = re.compile(
    r"需复核|待复核|人工确认|人工打开|手动打开|打开课件确认|TODO|FIXME|TBD|"
    r"待补|待完善|占位|例题模板|高频答题模板|空话|套话|\.\.\.|�"
    r"|严格逐句核对补充"
)
FIXED_PSEUDO_QUESTION_RE = re.compile(
    r"解决的核心问题是什么？它和本课程前后章节的哪个概念最容易混淆？"
)
ORDINARY_AUDIT_RESIDUE_PATTERNS = (
    ("UNVERIFIED marker", re.compile(r"\bUNVERIFIED\b")),
    ("page-level supplement heading", re.compile(r"^#{1,6}\s+.*页级补充\s*$", re.MULTILINE)),
    (
        "page-level evidence label",
        re.compile(
            r"^(?:\s*[-*]\s*)?(?:\*\*)?(?:页级证据|页级公式/边界证据)(?:\*\*)?\s*[:：]",
            re.MULTILINE,
        ),
    ),
    (
        "formal page-level source claim",
        re.compile(r"(?:^\s*(?:[-*]\s*)?正式页级来源\s*[:：]|20\d{2}\s*(?:年)?\s*正式页级来源(?:是|另见))", re.MULTILINE),
    ),
    (
        "page-level mainline claim",
        re.compile(
            r"(?:^\s*(?:[-*]\s*)?页级主线\s*[:：]|20\d{2}\s*(?:年)?\s*Lecture\s+\d+\s+的页级主线是)",
            re.MULTILINE,
        ),
    ),
    (
        "representative page-level claim",
        re.compile(r"代表页级(?:例子|公式)(?:/示例)?(?:是|见|\s*[:：])"),
    ),
    (
        "coverage weak-hit residue",
        re.compile(r"(?:覆盖审查[^\n]{0,80}原关键词弱命中|原关键词弱命中[^\n]{0,80}覆盖审查)"),
    ),
)
ORDINARY_AUDIT_EXEMPT_ROOTS = {"agent", "模板", "scripts", "tests"}
PYTHON_FENCE_RE = re.compile(r"^```python[^\n]*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)
MIN_NOTE_CHARS = {
    "concept_index": 800,
    "course_note": 600,
    "paper_note": 2500,
    "paper_topic_note": 800,
    "research_method_note": 1500,
    "review_compact": 1200,
    "review_detailed": 5000,
}


def has_bad_control_char(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if code < 32 and ch not in "\n\r\t":
            return True
    return False


def python_fence_syntax_issues(text: str) -> list[tuple[int, str]]:
    issues: list[tuple[int, str]] = []
    for match in PYTHON_FENCE_RE.finditer(text):
        line_no = text.count("\n", 0, match.start(1)) + 1
        try:
            ast.parse(match.group(1))
        except SyntaxError as exc:
            relative_line = exc.lineno or 1
            message = exc.msg or "invalid syntax"
            issues.append((line_no + relative_line - 1, message))
    return issues


def depth_issue(note_type: str, text: str) -> str | None:
    minimum = MIN_NOTE_CHARS.get(note_type)
    if minimum is None:
        return None
    body = strip_frontmatter(text)
    compact = re.sub(r"\s+", "", text_without_code(body))
    if len(compact) < minimum:
        return f"standalone depth {len(compact)} compact chars is below {minimum} for {note_type}"
    return None


def ordinary_audit_exempt(relative: str) -> bool:
    """Return whether a path is authoritative source metadata or supporting material."""
    path = Path(relative)
    if path.name == "source_manifest.md":
        return True
    if path.parts and path.parts[0] in ORDINARY_AUDIT_EXEMPT_ROOTS:
        return True
    return relative == "AGENT.md"


def content_policy_issues(relative: str, text: str) -> list[str]:
    """Check exact audit residue without rejecting natural source/page references."""
    prose = text_without_code(strip_frontmatter(text))
    issues: list[str] = []
    if Path(relative).name == "99_内容覆盖审查.md" and not ordinary_audit_exempt(relative):
        issues.append("1: forbidden legacy audit artifact")
    if not ordinary_audit_exempt(relative):
        for label, pattern in ORDINARY_AUDIT_RESIDUE_PATTERNS:
            for match in pattern.finditer(prose):
                line_no = prose.count("\n", 0, match.start()) + 1
                issues.append(f"{line_no}: ordinary-note audit residue ({label})")
    for match in FIXED_PSEUDO_QUESTION_RE.finditer(prose):
        line_no = prose.count("\n", 0, match.start()) + 1
        issues.append(f"{line_no}: fixed pseudo-question")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    files = markdown_files()
    index = build_note_index()
    issues: list[str] = []
    checked_links = 0
    broken_links = 0
    self_links = 0
    ambiguous_links = 0

    for path in files:
        text = read_text(path)
        prose_text = text_without_code(text)
        note_type = infer_note_type(path)
        issues.extend(f"{rel(path)}:{issue}" for issue in content_policy_issues(rel(path), text))
        if not text.strip():
            issues.append(f"{rel(path)}: empty file")
        if "<<<<<<<" in text or "=======" in text and ">>>>>>>" in text:
            issues.append(f"{rel(path)}: possible conflict marker")
        if text.count("```") % 2:
            issues.append(f"{rel(path)}: unbalanced code fence")
        if prose_text.count("$$") % 2:
            issues.append(f"{rel(path)}: unbalanced block math delimiter")
        if has_bad_control_char(text):
            issues.append(f"{rel(path)}: control character found")
        if issue := depth_issue(note_type, text):
            issues.append(f"{rel(path)}: {issue}")
        for line_no, message in python_fence_syntax_issues(text):
            issues.append(f"{rel(path)}:{line_no}: invalid python fence: {message}")
        if rel(path) != "AGENT.md" and not rel(path).startswith("agent/"):
            for match in RESIDUE_RE.finditer(prose_text):
                line_no = prose_text.count("\n", 0, match.start()) + 1
                issues.append(f"{rel(path)}:{line_no}: residue marker {match.group(0)}")
        for line_no, line in enumerate(text.splitlines(), 1):
            if line.startswith(("|---", "| ---", "| --")) and "解析：" in line:
                issues.append(f"{rel(path)}:{line_no}: table separator row contains 解析")
        for raw, target in wikilinks(text):
            checked_links += 1
            matches = wikilink_matches(target, path, index)
            if not matches:
                broken_links += 1
                issues.append(f"{rel(path)}: broken link [[{raw}]]")
            elif len(matches) > 1:
                ambiguous_links += 1
                choices = ", ".join(rel(item) for item in matches)
                issues.append(f"{rel(path)}: ambiguous link [[{raw}]] -> {choices}")
            elif matches[0] == path:
                self_links += 1
                issues.append(f"{rel(path)}: self link [[{raw}]]")

    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, text=True, capture_output=True)
    if diff_check.returncode:
        issues.append("git diff --check failed")

    payload = {
        "markdown_files": len(files),
        "checked_links": checked_links,
        "broken_links": broken_links,
        "self_links": self_links,
        "ambiguous_links": ambiguous_links,
        "core_issues": len(issues),
        "git_diff_check": diff_check.returncode == 0,
        "issues": issues[:100],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"markdown_files {payload['markdown_files']}")
        print(f"checked_links {checked_links}")
        print(f"broken_links {broken_links}")
        print(f"self_links {self_links}")
        print(f"ambiguous_links {ambiguous_links}")
        print(f"core_issues {len(issues)}")
        for issue in issues[:100]:
            print(f"ISSUE {issue}")
        if diff_check.returncode:
            print(diff_check.stdout, end="")
            print(diff_check.stderr, end="")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
