#!/usr/bin/env python3
"""Apply checks for non-course directories without forcing course templates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from check_frontmatter import parse_keys, unquote
from notes_utils import (
    ROOT,
    is_directory_without_symlinks,
    is_regular_file_without_symlinks,
    markdown_files,
    read_text,
    rel,
    split_frontmatter,
    strip_frontmatter,
)

SPECIAL_DIRS = [
    "概念索引",
    "游戏数值策划",
    "科研方法论",
    "计算机视觉/图像Raw域去噪",
    "学习路径",
    "算法岗学习笔记",
]
TEMPLATE_DIR = ".obsidian/templates"
REQUIRED_SPECIAL_ENTRIES = {"算法岗学习笔记": {"00_算法岗学习地图.md"}}
REQUIRED_NOTE_CONTRACTS = {
    "机器学习26/机器学习26考试复习笔记_按考点范围.md": {
        "note_type": "exam_review",
        "type_tag": "type/exam_review",
    }
}
EXPECTED_TEMPLATES = {
    "algorithm_error_log.md",
    "course_note.md",
    "paper_note.md",
    "concept_note.md",
    "source_manifest.md",
    "review_compact.md",
    "review_detailed.md",
    "game_design_note.md",
    "exam_review.md",
}


def nonempty_lines(path: Path) -> int:
    return sum(1 for line in strip_frontmatter(read_text(path)).splitlines() if line.strip())


def required_entry_issues(root: Path, directory: str) -> list[str]:
    base = root / directory
    return [
        f"{directory}/{name}: missing required special-directory entry"
        for name in sorted(REQUIRED_SPECIAL_ENTRIES.get(directory, set()))
        if not is_regular_file_without_symlinks(base / name, root)
    ]


def frontmatter_list_values(header: list[str], key: str) -> list[str]:
    for index, line in enumerate(header):
        if not line.startswith(f"{key}:"):
            continue
        values: list[str] = []
        for following in header[index + 1 :]:
            if not following.startswith("  - "):
                break
            values.append(unquote(following[4:].strip()))
        return values
    return []


def required_note_contract_issues(root: Path, relative_path: str) -> list[str]:
    expected = REQUIRED_NOTE_CONTRACTS[relative_path]
    path = root / relative_path
    if not is_regular_file_without_symlinks(path, root):
        return [f"{relative_path}: missing required contract note"]

    header, _body = split_frontmatter(read_text(path))
    keys = parse_keys(header)
    actual_note_type = unquote(keys.get("note_type", "")) or "<missing>"
    type_tags = sorted(tag for tag in frontmatter_list_values(header, "tags") if tag.startswith("type/"))
    issues: list[str] = []
    if actual_note_type != expected["note_type"]:
        issues.append(
            f"{relative_path}: note_type must be {expected['note_type']!r}, got {actual_note_type!r}"
        )
    expected_tags = [expected["type_tag"]]
    if type_tags != expected_tags:
        issues.append(f"{relative_path}: type tags must be {expected_tags!r}, got {type_tags!r}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    issues: list[str] = []
    checked = 0
    for directory in SPECIAL_DIRS:
        base = ROOT / directory
        if not is_directory_without_symlinks(base, ROOT):
            issues.append(f"{directory}: missing or symlinked special directory")
            continue
        checked += 1
        issues.extend(required_entry_issues(ROOT, directory))

    template_base = ROOT / TEMPLATE_DIR
    if not is_directory_without_symlinks(template_base, ROOT):
        issues.append(f"{TEMPLATE_DIR}: missing or symlinked template directory")
    else:
        existing = {
            path.name
            for path in template_base.glob("*.md")
            if is_regular_file_without_symlinks(path, ROOT)
        }
        for name in sorted(EXPECTED_TEMPLATES - existing):
            issues.append(f"{TEMPLATE_DIR}/{name}: missing required note template")
        for path in sorted(template_base.glob("*.md")):
            if not is_regular_file_without_symlinks(path, ROOT):
                continue
            header, body = split_frontmatter(read_text(path))
            keys = parse_keys(header)
            if unquote(keys.get("note_type", "")) != "template":
                issues.append(f"{rel(path)}: note_type must be 'template'")
            if "在此填写" in strip_frontmatter(read_text(path)) or "必填字段说明" in body:
                issues.append(f"{rel(path)}: visible template instruction residue")

    for relative_path in REQUIRED_NOTE_CONTRACTS:
        issues.extend(required_note_contract_issues(ROOT, relative_path))

    for path in markdown_files():
        r = rel(path)
        if r.startswith("概念索引/") and path.name == "source_manifest.md":
            issues.append(f"{r}: concept index should not use source_manifest.md")
        if r.startswith("游戏数值策划/表格模板/") and nonempty_lines(path) < 6:
            issues.append(f"{r}: table template entry is too short for Obsidian use")
        if r.startswith("科研方法论/") and any(term in read_text(path) for term in ["每周复盘模板", "达标标准"]):
            issues.append(f"{r}: research-method note contains generic study-plan template wording")
        if r.startswith("计算机视觉/图像Raw域去噪/"):
            header, _ = split_frontmatter(read_text(path))
            keys = {line.split(":", 1)[0].strip() for line in header if ":" in line and not line.startswith(" ")}
            if "source_url" in keys and "source_type" not in keys:
                issues.append(f"{r}: source_url exists but source_type is missing")

    payload = {"special_dirs_checked": checked, "special_dir_issues": len(issues), "issues": issues[:100]}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"special_dirs_checked {checked}")
        print(f"special_dir_issues {len(issues)}")
        for issue in issues[:100]:
            print(f"ISSUE {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
