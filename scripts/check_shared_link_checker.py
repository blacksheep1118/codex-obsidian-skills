#!/usr/bin/env python3
"""Ensure every bundled Obsidian link checker matches the shared copy."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "scripts" / "check_obsidian_links.py"
COPIES = [
    ROOT / "skill" / "ppt-to-md-for-obsidian" / "scripts" / "check_obsidian_links.py",
    ROOT / "skill" / "obsidian-vault-organizer" / "scripts" / "check_obsidian_links.py",
]


def normalized_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def main() -> int:
    canonical = normalized_text(CANONICAL)
    mismatches = []

    for path in COPIES:
        if not path.exists():
            mismatches.append(f"missing: {path.relative_to(ROOT)}")
            continue
        if normalized_text(path) != canonical:
            mismatches.append(f"out of sync: {path.relative_to(ROOT)}")

    if mismatches:
        print("shared_link_checker_validation failed", file=sys.stderr)
        for mismatch in mismatches:
            print(f"ERROR: {mismatch}", file=sys.stderr)
        return 1

    print("shared_link_checker_validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
