#!/usr/bin/env python3
"""Check lightweight quality issues in an Obsidian-style Markdown vault."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re


TEMPLATE_RE = re.compile(r"(相关知识链接|TODO|FIXME|TBD|待补|待完善)")


@dataclass(frozen=True)
class VaultIssue:
    path: Path
    kind: str
    message: str


def markdown_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if ".git" not in path.parts)


def relative_issue(root: Path, path: Path, kind: str, message: str) -> VaultIssue:
    return VaultIssue(path.relative_to(root), kind, message)


def is_conflict_marker(line: str, has_conflict_edges: bool) -> bool:
    stripped = line.strip()
    return stripped.startswith("<<<<<<<") or stripped.startswith(">>>>>>>") or (has_conflict_edges and stripped == "=======")


def find_vault_issues(root: Path, allow_duplicate_stems: bool = False) -> list[VaultIssue]:
    files = markdown_files(root)
    issues: list[VaultIssue] = []
    stems: dict[str, list[Path]] = {}

    for path in files:
        stems.setdefault(path.stem, []).append(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        stripped = text.strip()
        has_conflict_edges = "<<<<<<<" in text and ">>>>>>>" in text

        if not stripped:
            issues.append(relative_issue(root, path, "empty_file", "Markdown file has no content"))
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            if is_conflict_marker(line, has_conflict_edges):
                issues.append(relative_issue(root, path, "conflict_marker", f"line {line_number} contains merge conflict marker"))
            if TEMPLATE_RE.search(line):
                issues.append(relative_issue(root, path, "template_residue", f"line {line_number} contains leftover template text"))

        fence_count = sum(1 for line in text.splitlines() if line.strip().startswith("```"))
        if fence_count % 2:
            issues.append(relative_issue(root, path, "unbalanced_fence", "odd number of fenced code block delimiters"))

        if text.count("$$") % 2:
            issues.append(relative_issue(root, path, "unbalanced_math", "odd number of block math delimiters"))

    if not allow_duplicate_stems:
        for stem, paths in sorted(stems.items()):
            if len(paths) <= 1:
                continue
            joined = ", ".join(str(path.relative_to(root)) for path in paths)
            issues.append(VaultIssue(Path(stem), "duplicate_stem", f"duplicate note stem across files: {joined}"))

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Markdown vault quality issues.")
    parser.add_argument("root", type=Path, help="Vault or notes directory")
    parser.add_argument("--allow-duplicate-stems", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.exists():
        parser.error(f"directory does not exist: {root}")
    if not root.is_dir():
        parser.error(f"root must be a directory: {root}")

    issues = find_vault_issues(root, allow_duplicate_stems=args.allow_duplicate_stems)
    print(f"vault_quality_issues {len(issues)}")
    for issue in issues:
        print(f"{issue.kind.upper()}: {issue.path}: {issue.message}")

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
