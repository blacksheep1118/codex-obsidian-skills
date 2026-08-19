#!/usr/bin/env python3
"""Check Markdown table structure without altering note content."""

from __future__ import annotations

import argparse
import json
import sys

from notes_utils import is_table_separator, markdown_files, read_text, rel, table_split_unescaped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    issues: list[str] = []
    table_count = 0
    for path in markdown_files():
        lines = read_text(path).splitlines()
        active_cols: int | None = None
        for i, line in enumerate(lines, 1):
            if not line.startswith("|") or not line.endswith("|"):
                active_cols = None
                continue
            cells = table_split_unescaped(line)
            if not cells:
                active_cols = None
                continue
            if i + 1 <= len(lines) and is_table_separator(lines[i]):
                table_count += 1
                active_cols = len(cells)
                continue
            if is_table_separator(line):
                if active_cols is not None and len(cells) != active_cols:
                    issues.append(f"{rel(path)}:{i}: separator column count mismatch")
                continue
            if active_cols is not None and len(cells) != active_cols:
                issues.append(f"{rel(path)}:{i}: table row has {len(cells)} columns, expected {active_cols}")

    payload = {"tables_checked": table_count, "table_issues": len(issues), "issues": issues[:100]}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"tables_checked {table_count}")
        print(f"table_issues {len(issues)}")
        for issue in issues[:100]:
            print(f"ISSUE {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
