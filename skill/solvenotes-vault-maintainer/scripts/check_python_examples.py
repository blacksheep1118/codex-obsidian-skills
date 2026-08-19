#!/usr/bin/env python3
"""Parse Python fenced examples without executing them."""

from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

PYTHON_BLOCK_RE = re.compile(
    r"^```(?:python|python3|py)(?:[ \t]+[^\n]*)?\n(.*?)^```[ \t]*$",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)


def python_blocks(text: str) -> list[tuple[int, str]]:
    """Return Python fenced blocks and their one-based opening line numbers."""

    blocks: list[tuple[int, str]] = []
    for match in PYTHON_BLOCK_RE.finditer(text):
        blocks.append((text[: match.start()].count("\n") + 1, match.group(1)))
    return blocks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True, help="notes vault root")
    args = parser.parse_args()

    discovered: list[tuple[Path, int, str]] = []
    for path in sorted(args.root.rglob("*.md")):
        if ".obsidian/templates" in path.as_posix():
            continue
        for line, code in python_blocks(path.read_text(encoding="utf-8")):
            discovered.append((path, line, code))

    failures: list[str] = []
    for path, line, code in discovered:
        try:
            ast.parse(code, filename=f"{path}:{line}", type_comments=True)
        except SyntaxError as error:
            label = f"{path.relative_to(args.root)}:{line}"
            failures.append(f"{label}: {error.msg} (line {error.lineno})")

    print(
        "python_examples "
        f"fenced_blocks={len(discovered)} "
        f"parsed={len(discovered) - len(failures)} "
        f"failures={len(failures)}"
    )
    for failure in failures:
        print(f"FAIL {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
