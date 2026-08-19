#!/usr/bin/env python3
"""Validate Obsidian wiki links."""

from __future__ import annotations

import argparse
import json
import sys

from notes_utils import ROOT, build_note_index, markdown_files, read_text, rel, wikilink_matches, wikilinks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    index = build_note_index()
    checked = 0
    broken: list[str] = []
    self_links: list[str] = []
    ambiguous: list[str] = []

    for path in markdown_files():
        text = read_text(path)
        for raw, target in wikilinks(text):
            checked += 1
            matches = wikilink_matches(target, path, index)
            if not matches:
                broken.append(f"{rel(path)} -> [[{raw}]]")
            elif len(matches) > 1:
                choices = ", ".join(rel(item) for item in matches)
                ambiguous.append(f"{rel(path)} -> [[{raw}]] -> {choices}")
            elif matches[0] == path:
                self_links.append(f"{rel(path)} -> [[{raw}]]")

    payload = {
        "checked_links": checked,
        "broken_links": len(broken),
        "self_links": len(self_links),
        "ambiguous_links": len(ambiguous),
        "broken": broken[:50],
        "self": self_links[:50],
        "ambiguous": ambiguous[:50],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"checked_links {checked}")
        print(f"broken_links {len(broken)}")
        print(f"self_links {len(self_links)}")
        print(f"ambiguous_links {len(ambiguous)}")
        for item in broken[:50]:
            print(f"BROKEN {item}")
        for item in self_links[:50]:
            print(f"SELF {item}")
        for item in ambiguous[:50]:
            print(f"AMBIGUOUS {item}")
    if broken or self_links or ambiguous:
        if not args.json:
            print(f"vault_root {ROOT}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
