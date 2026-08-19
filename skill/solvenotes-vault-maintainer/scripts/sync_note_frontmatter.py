#!/usr/bin/env python3
"""Add or refresh lightweight frontmatter for every Markdown note."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

from notes_utils import (
    ROOT,
    infer_note_type,
    is_reserved_agent_rule_name,
    manifest_rows,
    markdown_files,
    note_title,
    read_text,
    read_text_with_version,
    rel,
    split_frontmatter,
    write_text_if_changed,
)

MANAGED_KEYS = {"course", "note_type", "aliases", "source_files", "coverage", "last_checked", "tags"}
ALIASES_NOTE_TYPES = {"course_note"}


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def remove_managed(lines: list[str]) -> list[str]:
    kept: list[str] = []
    skip_list = False
    for line in lines:
        if skip_list:
            if line.startswith("  - "):
                continue
            skip_list = False
        key = line.split(":", 1)[0].strip() if ":" in line and not line.startswith(" ") else ""
        if key in MANAGED_KEYS:
            skip_list = key in {"aliases", "source_files", "tags"}
            continue
        kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    return kept


def yaml_unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def parse_list_value(lines: list[str], key: str) -> list[str]:
    values: list[str] = []
    for idx, line in enumerate(lines):
        if not line.startswith(f"{key}:"):
            continue
        value = line.split(":", 1)[1].strip()
        if value == "[]":
            return []
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                return []
            return [yaml_unquote(item.strip()) for item in inner.split(",") if item.strip()]
        next_idx = idx + 1
        while next_idx < len(lines) and lines[next_idx].startswith("  - "):
            values.append(yaml_unquote(lines[next_idx][4:].strip()))
            next_idx += 1
        return values
    return []


def parse_scalar_value(lines: list[str], key: str) -> str | None:
    for line in lines:
        if line.startswith(f"{key}:"):
            value = yaml_unquote(line.split(":", 1)[1].strip())
            return value or None
    return None


def checked_date_for(lines: list[str], requested_date: str | None) -> str:
    if requested_date:
        return requested_date
    existing = parse_scalar_value(lines, "last_checked")
    if existing:
        return existing
    raise ValueError("missing last_checked; pass --date YYYY-MM-DD explicitly")


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        value = value.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def source_mapping() -> dict[str, list[str]]:
    mapping: dict[str, set[str]] = defaultdict(set)
    for _, cells in manifest_rows():
        if len(cells) < 5:
            continue
        source = cells[0].strip("`")
        note_cell = cells[4]
        for raw in re.findall(r"\[\[([^\]]+)\]\]", note_cell):
            target = raw.split("|", 1)[0].split("#", 1)[0].strip()
            if target:
                mapping[target].add(source)
                mapping[f"{target}.md"].add(source)
    normalized: dict[str, list[str]] = {}
    for path in markdown_files():
        relative = rel(path)
        no_suffix = relative[:-3] if relative.endswith(".md") else relative
        sources = sorted(mapping.get(relative, set()) | mapping.get(no_suffix, set()))
        normalized[relative] = sources
    return normalized


def course_for(path: Path) -> str:
    parts = path.relative_to(ROOT).parts
    if len(parts) == 1 and is_reserved_agent_rule_name(parts[0]):
        return "仓库规则"
    if len(parts) == 1:
        return "全仓"
    return parts[0]


def coverage_for(path: Path, sources: list[str]) -> str:
    note_type = infer_note_type(path)
    if note_type in {
        "source_manifest",
        "source_manifest_history",
        "coverage_audit",
        "vault_audit",
        "global_coverage_audit",
    }:
        return "checked"
    if sources:
        return "source_mapped"
    if note_type in {"agent_rule", "concept_index", "game_design_note", "research_method_note", "paper_topic_note", "template"}:
        return "special_rule"
    return "checked"


def tag_value(value: str) -> str:
    value = re.sub(r"\s+", "_", value.strip())
    value = value.replace("#", "")
    return value or "unknown"


def aliases_for(path: Path, text: str, existing: list[str]) -> list[str]:
    if infer_note_type(path) not in ALIASES_NOTE_TYPES:
        return dedupe(existing)
    return dedupe(existing + [note_title(path, text), path.stem])


def tags_for(path: Path, course: str, note_type: str, existing: list[str]) -> list[str]:
    managed = [f"course/{tag_value(course)}", f"type/{tag_value(note_type)}"]
    unmanaged = [tag for tag in existing if not tag.startswith(("course/", "type/"))]
    return dedupe(unmanaged + managed)


def append_yaml_list(lines: list[str], key: str, values: list[str]) -> None:
    if not values:
        return
    lines.append(f"{key}:")
    lines.extend(f"  - {yaml_quote(value)}" for value in values)


def managed_block(
    path: Path,
    text: str,
    sources: list[str],
    checked_date: str,
    existing_aliases: list[str],
    existing_tags: list[str],
) -> list[str]:
    course = course_for(path)
    note_type = infer_note_type(path)
    lines = [
        f"course: {yaml_quote(course)}",
        f"note_type: {yaml_quote(note_type)}",
    ]
    append_yaml_list(lines, "aliases", aliases_for(path, text, existing_aliases))
    if sources:
        lines.append("source_files:")
        lines.extend(f"  - {yaml_quote(source)}" for source in sources)
    else:
        lines.append("source_files: []")
    lines.append(f"coverage: {yaml_quote(coverage_for(path, sources))}")
    lines.append(f"last_checked: {yaml_quote(checked_date)}")
    append_yaml_list(lines, "tags", tags_for(path, course, note_type, existing_tags))
    return lines


def normalized_text(
    path: Path,
    checked_date: str | None,
    source_map: dict[str, list[str]],
    text: str | None = None,
) -> str:
    text = read_text(path) if text is None else text
    header, body = split_frontmatter(text)
    effective_date = checked_date_for(header, checked_date)
    existing_aliases = parse_list_value(header, "aliases")
    existing_tags = parse_list_value(header, "tags")
    kept = remove_managed(header)
    sources = source_map.get(rel(path), [])
    new_header = kept + ([""] if kept else []) + managed_block(
        path,
        text,
        sources,
        effective_date,
        existing_aliases,
        existing_tags,
    )
    return "---\n" + "\n".join(new_header) + "\n---\n\n" + body.lstrip("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if frontmatter is stale")
    parser.add_argument(
        "--date",
        default=None,
        help="set last_checked explicitly; otherwise preserve each note's existing date",
    )
    args = parser.parse_args()

    source_map = source_mapping()
    changed: list[str] = []
    for path in markdown_files():
        if rel(path).startswith("模板/"):
            continue
        original_text, original_version = read_text_with_version(path)
        new_text = normalized_text(path, args.date, source_map, original_text)
        if original_text != new_text:
            changed.append(rel(path))
            if not args.check:
                write_text_if_changed(path, new_text, expected_version=original_version)

    print(f"frontmatter_files_checked {len(markdown_files())}")
    print(f"frontmatter_files_changed {len(changed)}")
    for item in changed[:100]:
        print(f"CHANGED {item}")
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    sys.exit(main())
