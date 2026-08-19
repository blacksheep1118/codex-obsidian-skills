#!/usr/bin/env python3
"""Normalize source_manifest.md formatting without inventing evidence fields."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from notes_utils import (
    DEFAULT_LAST_CHECKED,
    ROOT,
    formal_source_manifests,
    is_table_separator,
    read_text_with_version,
    split_table_row,
    write_text_if_changed,
)

STANDARD_HEADER = "| 源文件 | 类型 | 页/slide/记录数 | 抽取方式 | 对应笔记 | 覆盖状态 | 例题状态 | 限制说明 | 最后检查日期 |"
STANDARD_SEPARATOR = "|---|---|---:|---|---|---|---|---|---|"


class UnsafeLegacyRowError(ValueError):
    """Raised when a legacy row lacks fields that require source evidence."""


def source_manifest_paths(root: Path = ROOT) -> list[Path]:
    """Return exactly the formal manifests governed by the source contract.

    Formatting must cover nested study topics and must never rewrite the
    template scaffold.  Keep this enumeration shared with source coverage and
    strict source-file checks instead of maintaining a separate glob here.
    """

    return formal_source_manifests(root)


def normalize_line(line: str, checked_date: str) -> str:
    if line.startswith("| 源文件 |"):
        return STANDARD_HEADER
    if not line.startswith("| `"):
        return line
    cells = split_table_row(line)
    if len(cells) == 9:
        return "| " + " | ".join(cells) + " |"
    if len(cells) == 6:
        source = cells[0]
        raise UnsafeLegacyRowError(
            f"legacy 6-column row {source} needs manual coverage, example, limitation, and checked-date evidence"
        )
    return line


def normalized_text(text: str, checked_date: str) -> str:
    normalized: list[str] = []
    in_local_source_table = False
    for line in text.splitlines():
        if line.startswith("| 源文件 |"):
            in_local_source_table = True
            normalized.append(normalize_line(line, checked_date))
        elif in_local_source_table and is_table_separator(line):
            normalized.append(STANDARD_SEPARATOR)
        elif in_local_source_table and line.startswith("|"):
            normalized.append(normalize_line(line, checked_date))
        elif line.startswith("| `"):
            # A backticked source row outside a recognized header is legacy
            # local-manifest input: preserve its fail-closed six-column error.
            normalized.append(normalize_line(line, checked_date))
        else:
            in_local_source_table = False
            normalized.append(line)
    return "\n".join(normalized) + ("\n" if text.endswith("\n") else "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if manifests are not normalized")
    parser.add_argument("--date", default=DEFAULT_LAST_CHECKED)
    args = parser.parse_args()

    changed: list[str] = []
    unsafe: list[str] = []
    manifests = source_manifest_paths()
    for path in manifests:
        try:
            original_text, original_version = read_text_with_version(path)
            new_text = normalized_text(original_text, args.date)
        except UnsafeLegacyRowError as exc:
            unsafe.append(f"{path.relative_to(ROOT).as_posix()}: {exc}")
            continue
        if original_text != new_text:
            changed.append(path.relative_to(ROOT).as_posix())
            if not args.check:
                write_text_if_changed(path, new_text, expected_version=original_version)

    print(f"source_manifests_checked {len(manifests)}")
    print(f"source_manifests_changed {len(changed)}")
    for item in changed[:50]:
        print(f"CHANGED {item}")
    print(f"source_manifests_unsafe {len(unsafe)}")
    for item in unsafe[:50]:
        print(f"UNSAFE {item}")
    return 1 if unsafe or (args.check and changed) else 0


if __name__ == "__main__":
    sys.exit(main())
