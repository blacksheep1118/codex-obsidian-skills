#!/usr/bin/env python3
"""Audit or explicitly remove page-level coverage sections from regular notes.

The old workflow wrapped these sections in stable markers inside chapter notes.
They are audit residue, not study material, so the repository keeps them out of
user-facing notes and retains necessary source boundaries in source_manifest.md.
"""

from __future__ import annotations

import argparse
import sys

from notes_utils import infer_note_type, markdown_files, read_text_with_version, rel, write_text_if_changed

HEADING = "## PPT/PDF 页级补充索引"
START = "<!-- source-coverage:start -->"
END = "<!-- source-coverage:end -->"
SKIP_NOTE_TYPES = {
    "agent_rule",
    "source_manifest",
    "template",
    "vault_audit",
}


def regular_note(path) -> bool:
    return infer_note_type(path) not in SKIP_NOTE_TYPES


def remove_section(lines: list[str], start: int) -> tuple[list[str], int, bool]:
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    before = lines[:start]
    after = lines[end:]
    while before and not before[-1].strip():
        before.pop()
    while after and not after[0].strip():
        after.pop(0)
    if before and after:
        before.append("")
    return before + after, start, True


def remove_visible_sections(text: str) -> tuple[str, bool]:
    lines = text.splitlines()
    i = 0
    changed = False
    while i < len(lines):
        if lines[i] == HEADING:
            lines, i, section_changed = remove_section(lines, i)
            changed = changed or section_changed
            continue
        i += 1
    if not changed:
        return text, False
    return "\n".join(lines) + ("\n" if text.endswith("\n") else ""), True


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="fail if regular notes contain visible source coverage blocks")
    mode.add_argument("--apply", action="store_true", help="explicitly delete matching sections from regular notes")
    args = parser.parse_args()

    changed: list[str] = []
    for path in markdown_files():
        original_text, original_version = read_text_with_version(path)
        if not regular_note(path):
            continue
        new_text, was_changed = remove_visible_sections(original_text)
        if was_changed:
            changed.append(rel(path))
            if args.apply:
                write_text_if_changed(path, new_text, expected_version=original_version)

    action = "removed" if args.apply else "found"
    print(f"source_coverage_note_blocks_{action} {len(changed)}")
    for item in changed[:100]:
        print(f"{action.upper()} {item}")
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    sys.exit(main())
