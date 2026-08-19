#!/usr/bin/env python3
"""Compile and run only explicitly marked, self-contained C++17 note examples."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

MARKER = "<!-- runnable: cpp17 -->"
CPP_BLOCK_RE = re.compile(r"```cpp[^\n]*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)


def marked_blocks(text: str) -> list[tuple[int, str]]:
    blocks: list[tuple[int, str]] = []
    for match in CPP_BLOCK_RE.finditer(text):
        prefix = text[: match.start()]
        if prefix.rstrip().endswith(MARKER):
            blocks.append((prefix.count("\n") + 1, match.group(1)))
    return blocks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True, help="notes vault root")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()
    compiler = shutil.which("g++")
    paths = sorted(args.root.rglob("*.md"))
    discovered: list[tuple[Path, int, str]] = []
    for path in paths:
        for line, code in marked_blocks(path.read_text(encoding="utf-8")):
            discovered.append((path, line, code))
    if compiler is None:
        print(f"cpp_examples skipped compiler_missing marked_blocks={len(discovered)}")
        return 0
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="solvenotes-cpp-") as temp_dir:
        temp = Path(temp_dir)
        for index, (path, line, code) in enumerate(discovered, 1):
            source = temp / f"example_{index}.cpp"
            binary = temp / f"example_{index}"
            source.write_text(code, encoding="utf-8")
            compile_result = subprocess.run(
                [compiler, "-std=c++17", "-Wall", "-Wextra", "-pedantic", str(source), "-o", str(binary)],
                capture_output=True,
                text=True,
                timeout=args.timeout,
            )
            label = f"{path.relative_to(args.root)}:{line}"
            if compile_result.returncode:
                failures.append(f"{label}: compile\n{compile_result.stderr.strip()}")
                continue
            try:
                run_result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=args.timeout)
            except subprocess.TimeoutExpired:
                failures.append(f"{label}: run timeout")
                continue
            if run_result.returncode:
                failures.append(f"{label}: run exit {run_result.returncode}\n{run_result.stderr.strip()}")
    print(f"cpp_examples marked_blocks={len(discovered)} compiled={len(discovered) - len(failures)} failures={len(failures)}")
    for failure in failures:
        print(f"FAIL {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
