#!/usr/bin/env python3
"""Validate lightweight frontmatter in every Markdown note."""

from __future__ import annotations

import argparse
import json
import re
import sys

from notes_utils import COVERAGE_VALUES, NOTE_TYPES, markdown_files, read_text, rel, split_frontmatter

REQUIRED_KEYS = ["course", "note_type", "source_files", "coverage", "last_checked"]
LIST_KEYS = {"aliases", "source_files", "tags"}
MANAGED_KEYS = set(REQUIRED_KEYS) | LIST_KEYS


def parse_keys(lines: list[str]) -> dict[str, str]:
    keys: dict[str, str] = {}
    for line in lines:
        if not line or line.startswith(" ") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        keys[key.strip()] = value.strip()
    return keys


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def has_yaml_list(lines: list[str], idx: int) -> bool:
    next_idx = idx + 1
    return next_idx < len(lines) and lines[next_idx].startswith("  - ")


def validate_frontmatter_structure(lines: list[str], path_label: str, issues: list[str]) -> None:
    seen_managed: set[str] = set()
    active_list_key: str | None = None

    for line_no, line in enumerate(lines, 1):
        if not line:
            active_list_key = None
            continue
        if line.startswith("  - "):
            if active_list_key not in LIST_KEYS:
                issues.append(f"{path_label}:{line_no}: YAML list item is not attached to aliases/source_files/tags")
            continue
        if line.startswith(" "):
            active_list_key = None
            issues.append(f"{path_label}:{line_no}: unknown indented frontmatter line")
            continue
        active_list_key = None
        if ":" not in line:
            issues.append(f"{path_label}:{line_no}: invalid frontmatter line")
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key in MANAGED_KEYS:
            if key in seen_managed:
                issues.append(f"{path_label}:{line_no}: duplicate managed frontmatter key {key}")
            seen_managed.add(key)
        if key in LIST_KEYS and value == "":
            active_list_key = key


def validate_list_field(lines: list[str], keys: dict[str, str], key: str, path_label: str, issues: list[str]) -> None:
    if key not in keys:
        return
    idx = next((i for i, line in enumerate(lines) if line.startswith(f"{key}:")), -1)
    if idx < 0:
        return
    value = keys[key]
    if value == "[]":
        return
    if value == "":
        if has_yaml_list(lines, idx):
            return
        issues.append(f"{path_label}: {key} must be [] or a YAML list")
        return
    issues.append(f"{path_label}: {key} must be [] or a YAML list")


def validate_source_files(lines: list[str], keys: dict[str, str], path_label: str, issues: list[str]) -> None:
    validate_list_field(lines, keys, "source_files", path_label, issues)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    issues: list[str] = []
    checked = 0
    for path in markdown_files():
        checked += 1
        header, _ = split_frontmatter(read_text(path))
        if not header:
            issues.append(f"{rel(path)}: missing frontmatter")
            continue
        keys = parse_keys(header)
        validate_frontmatter_structure(header, rel(path), issues)
        for key in REQUIRED_KEYS:
            if key not in keys:
                issues.append(f"{rel(path)}: missing frontmatter key {key}")
        if "note_type" in keys and unquote(keys["note_type"]) not in NOTE_TYPES:
            issues.append(f"{rel(path)}: invalid note_type {keys['note_type']}")
        if "coverage" in keys and unquote(keys["coverage"]) not in COVERAGE_VALUES:
            issues.append(f"{rel(path)}: invalid coverage {keys['coverage']}")
        if "last_checked" in keys and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", unquote(keys["last_checked"])):
            issues.append(f"{rel(path)}: last_checked must be YYYY-MM-DD")
        validate_source_files(header, keys, rel(path), issues)
        validate_list_field(header, keys, "aliases", rel(path), issues)
        validate_list_field(header, keys, "tags", rel(path), issues)

    payload = {"frontmatter_files_checked": checked, "frontmatter_issues": len(issues), "issues": issues[:100]}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"frontmatter_files_checked {checked}")
        print(f"frontmatter_issues {len(issues)}")
        for issue in issues[:100]:
            print(f"ISSUE {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
