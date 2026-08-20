#!/usr/bin/env python3
"""Check the small, versioned rule surface of an external Notes vault."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from check_frontmatter import parse_keys, unquote, validate_frontmatter_structure
from notes_utils import (
    build_note_index,
    is_directory_without_symlinks,
    is_regular_file_without_symlinks,
    is_reserved_agent_name,
    is_reserved_agent_rule_name,
    lexical_absolute_path,
    read_text,
    split_frontmatter,
    text_without_code,
    wikilink_matches,
    wikilinks,
)

REQUIRED_GUIDANCE_VALUES = {
    "course": "仓库规则",
    "note_type": "agent_rule",
    "source_files": "[]",
    "coverage": "special_rule",
}
REQUIRED_GUIDANCE_TAGS = {"course/仓库规则", "type/agent_rule"}
REQUIRED_KEYS = {"course", "note_type", "source_files", "coverage", "last_checked"}
RESERVED_MAINTENANCE_NAMES = {"scripts", "tests", ".githooks", "pyproject.toml"}
FENCE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})(.*)$")
CONFLICT_RE = re.compile(r"^(<<<<<<<|=======|>>>>>>>)", re.MULTILINE)
DEFAULT_GIT_AUTHORITY_RE = re.compile(r"默认[^。！？\n]{0,80}(?:提交|推送)")
AUTOMATIC_GIT_AUTHORITY_RE = re.compile(
    r"(?:自动(?:提交|推送)|"
    r"(?:无需|无须|不需要|不必)(?:用户)?(?:明确)?授权[^。！？\n]{0,20}(?:提交|推送)|"
    r"(?:提交|推送)[^。！？\n]{0,20}(?:无需|无须|不需要|不必)(?:用户)?(?:明确)?授权|"
    r"(?<!不)可(?:以)?直接(?:提交|推送))"
)


def relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def git_paths(root: Path, *arguments: str) -> tuple[set[str], str | None]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        return set(), detail or f"git ls-files exited {result.returncode}"
    return {
        item
        for item in result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
        if item
    }, None


def is_guidance_path(path: str) -> bool:
    return path == "AGENT.md"


def guidance_files(root: Path, tracked_paths: set[str] | None = None) -> list[Path]:
    if tracked_paths is None:
        tracked_paths, error = git_paths(root, "--cached")
        if error:
            return []
    return sorted(
        root / path
        for path in tracked_paths
        if is_guidance_path(path) and is_regular_file_without_symlinks(root / path, root)
    )


def guidance_boundary_issues(root: Path) -> list[str]:
    """Reject instruction objects and maintenance trees in the visible vault."""

    if not is_directory_without_symlinks(root, root):
        return [".: repository root must be a regular non-symlink directory"]

    issues: list[str] = []
    scan_errors: list[OSError] = []

    def record(error: OSError) -> None:
        scan_errors.append(error)

    for directory, dirnames, filenames in os.walk(root, topdown=True, onerror=record, followlinks=False):
        current = Path(directory)
        if current == root and ".git" in dirnames and not (current / ".git").is_symlink():
            dirnames.remove(".git")

        symlink_dirs = {name for name in dirnames if (current / name).is_symlink()}
        dirnames[:] = sorted(name for name in dirnames if name not in symlink_dirs)
        names = [*dirnames, *sorted(symlink_dirs), *sorted(filenames)]
        for name in names:
            path = current / name
            label = relative(root, path)
            if path.is_symlink():
                issues.append(f"{label}: symlink filesystem object is forbidden in notes vault")
                continue
            if name == ".git" and current != root:
                issues.append(f"{label}: nested .git filesystem object is forbidden")
            if is_reserved_agent_name(name):
                issues.append(f"{label}: forbidden agent filesystem object in notes vault")
            elif is_reserved_agent_rule_name(name):
                if current == root and name != "AGENT.md":
                    issues.append(f"{label}: root guidance must use canonical filename AGENT.md")
                elif current != root:
                    issues.append(f"{label}: additional AGENT.md is forbidden")
            if name in RESERVED_MAINTENANCE_NAMES:
                issues.append(
                    f"{label}: maintenance implementation must live in the external Solvenotes Skill, not /notes"
                )

    for error in scan_errors:
        filename = Path(error.filename) if error.filename else root
        try:
            label = relative(root, filename)
        except ValueError:
            label = str(filename)
        issues.append(f"{label}: cannot scan guidance boundary: {error.strerror or error}")
    return sorted(set(issues))


def yaml_list_values(lines: list[str], key: str) -> list[str] | None:
    for index, line in enumerate(lines):
        if not line.startswith(f"{key}:"):
            continue
        value = line.split(":", 1)[1].strip()
        if value == "[]":
            return []
        if value:
            return None
        values: list[str] = []
        for following in lines[index + 1 :]:
            if not following.startswith("  - "):
                break
            values.append(unquote(following[4:].strip()))
        return values
    return None


def valid_date(value: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate_guidance_frontmatter(root: Path, path: Path, text: str) -> list[str]:
    label = relative(root, path)
    header, _body = split_frontmatter(text)
    if not header:
        return [f"{label}: missing frontmatter"]
    issues: list[str] = []
    validate_frontmatter_structure(header, label, issues)
    keys = parse_keys(header)
    for key, expected in REQUIRED_GUIDANCE_VALUES.items():
        if key not in keys:
            issues.append(f"{label}: missing frontmatter key {key}")
            continue
        actual = keys[key] if key == "source_files" else unquote(keys[key])
        if actual != expected:
            issues.append(f"{label}: {key} must be {expected!r}, got {actual!r}")
    if "last_checked" not in keys:
        issues.append(f"{label}: missing frontmatter key last_checked")
    elif not valid_date(unquote(keys["last_checked"])):
        issues.append(f"{label}: last_checked must be a valid YYYY-MM-DD date")
    tags = yaml_list_values(header, "tags")
    if tags is None:
        issues.append(f"{label}: tags must be a YAML list")
    else:
        missing = sorted(REQUIRED_GUIDANCE_TAGS - set(tags))
        if missing:
            issues.append(f"{label}: missing required tags {', '.join(missing)}")
    return issues


def fence_scan(text: str) -> tuple[bool, str]:
    opening: str | None = None
    length = 0
    prose: list[str] = []
    for line in text.splitlines():
        match = FENCE_RE.match(line)
        if opening is None:
            if match:
                fence = match.group(1)
                opening, length = fence[0], len(fence)
                prose.append("")
            else:
                prose.append(line)
            continue
        if match:
            fence, tail = match.group(1), match.group(2)
            if fence[0] == opening and len(fence) >= length and not tail.strip():
                opening, length = None, 0
        prose.append("")
    return opening is not None, "\n".join(prose)


def validate_guidance_markdown(root: Path, path: Path, text: str) -> list[str]:
    label = relative(root, path)
    issues: list[str] = []
    unclosed, prose = fence_scan(text)
    if unclosed:
        issues.append(f"{label}: unclosed fenced code block")
    if prose.count("$$") % 2:
        issues.append(f"{label}: unbalanced block math delimiter outside code")
    if CONFLICT_RE.search(text):
        issues.append(f"{label}: possible conflict markers")
    if any(ord(char) < 32 and char not in "\n\r\t" for char in text):
        issues.append(f"{label}: illegal control character")
    return issues


def validate_root_git_authorization(root: Path, path: Path, text: str) -> list[str]:
    label = relative(root, path)
    prose = text_without_code(text)
    issues: list[str] = []
    for line_number, line in enumerate(prose.splitlines(), 1):
        if DEFAULT_GIT_AUTHORITY_RE.search(line):
            issues.append(f"{label}:{line_number}: default workflow must not grant commit or push authority")
        if AUTOMATIC_GIT_AUTHORITY_RE.search(line):
            issues.append(f"{label}:{line_number}: guidance must not grant automatic commit or push authority")
    sentences = re.split(r"[。！？\n]+", prose)
    explicit = any(
        "提交" in sentence
        and "推送" in sentence
        and "用户" in sentence
        and "授权" in sentence
        and re.search(r"必须|只有|仅(?:在|当)?|经", sentence)
        for sentence in sentences
    )
    if not explicit:
        issues.append(f"{label}: must explicitly require user authorization for commit and push")
    return issues


def guidance_link_issues(root: Path, path: Path, text: str) -> tuple[list[str], int]:
    index = build_note_index(root)
    issues: list[str] = []
    checked = 0
    for raw, target in wikilinks(text):
        checked += 1
        matches = wikilink_matches(target, path, index, root)
        if not matches:
            issues.append(f"{relative(root, path)}: broken wikilink [[{raw}]]")
        elif len(matches) > 1:
            choices = ", ".join(relative(root, item) for item in matches)
            issues.append(f"{relative(root, path)}: ambiguous wikilink [[{raw}]] -> {choices}")
    return issues, checked


def collect_guidance_report(root: Path) -> dict[str, object]:
    root = lexical_absolute_path(root)
    if not is_directory_without_symlinks(root, root):
        return {
            "guidance_files_checked": 0,
            "guidance_wikilinks_checked": 0,
            "guidance_supporting_files_checked": 0,
            "issues": [".: repository root must be a regular non-symlink directory"],
        }

    tracked, git_error = git_paths(root, "--cached")
    issues = guidance_boundary_issues(root)
    files = guidance_files(root, tracked if git_error is None else None)
    if not files:
        issues.append("AGENT.md: missing tracked root guidance file")

    checked_links = 0
    for path in files:
        text = read_text(path)
        issues.extend(validate_guidance_frontmatter(root, path, text))
        issues.extend(validate_guidance_markdown(root, path, text))
        issues.extend(validate_root_git_authorization(root, path, text))
        link_issues, count = guidance_link_issues(root, path, text)
        issues.extend(link_issues)
        checked_links += count

    if git_error is not None:
        issues.append(f"Git metadata unavailable: {git_error}")
    return {
        "guidance_files_checked": len(files),
        "guidance_wikilinks_checked": checked_links,
        "guidance_supporting_files_checked": 0,
        "guidance_full_commands": 0,
        "guidance_full_python_checks": 0,
        "issues": sorted(set(issues)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None, help="external notes vault root")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    raw_root = args.root or os.environ.get("SOLVENOTES_VAULT_ROOT")
    if not raw_root:
        parser.error("--root or SOLVENOTES_VAULT_ROOT is required")
    report = collect_guidance_report(Path(raw_root))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for key, value in report.items():
            if key != "issues":
                print(f"{key} {value}")
        print(f"guidance_issues {len(report['issues'])}")
        for issue in report["issues"]:
            print(f"ISSUE {issue}")
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    sys.exit(main())
