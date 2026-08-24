#!/usr/bin/env python3
"""Compile and run only explicitly marked, self-contained C++17 note examples."""

from __future__ import annotations

import argparse
import math
import re
import shutil
import tempfile
from pathlib import Path

try:
    from .run_with_timeout import run_capture
except ImportError:
    from run_with_timeout import run_capture

MARKER = "<!-- runnable: cpp17 -->"
CPP_BLOCK_RE = re.compile(r"```cpp[^\n]*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)
DEFAULT_TIMEOUT_SECONDS = 15.0


def positive_timeout(value: str) -> float:
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("timeout must be a finite number greater than zero")
    return timeout


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
    parser.add_argument("--timeout", type=positive_timeout, default=DEFAULT_TIMEOUT_SECONDS)
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
    compiled_count = 0
    with tempfile.TemporaryDirectory(prefix="solvenotes-cpp-") as temp_dir:
        temp = Path(temp_dir)
        for index, (path, line, code) in enumerate(discovered, 1):
            source = temp / f"example_{index}.cpp"
            binary = temp / f"example_{index}"
            source.write_text(code, encoding="utf-8")
            label = f"{path.relative_to(args.root)}:{line}"
            compile_result = run_capture(
                [compiler, "-std=c++17", "-Wall", "-Wextra", "-pedantic", str(source), "-o", str(binary)],
                args.timeout,
                f"compile {label}",
            )
            if compile_result.timed_out:
                failures.append(f"{label}: compile timeout")
                continue
            if compile_result.stdout_limit_exceeded or compile_result.stderr_limit_exceeded:
                failures.append(f"{label}: compile diagnostic output exceeded safety limit")
                continue
            if compile_result.returncode:
                stderr = compile_result.stderr.decode("utf-8", errors="replace").strip()
                failures.append(f"{label}: compile\n{stderr}")
                continue
            compiled_count += 1
            run_result = run_capture(
                [str(binary)],
                args.timeout,
                f"run {label}",
            )
            if run_result.timed_out:
                failures.append(f"{label}: run timeout")
                continue
            if run_result.stdout_limit_exceeded or run_result.stderr_limit_exceeded:
                failures.append(f"{label}: run output exceeded safety limit")
                continue
            if run_result.returncode:
                stderr = run_result.stderr.decode("utf-8", errors="replace").strip()
                failures.append(f"{label}: run exit {run_result.returncode}\n{stderr}")
    print(f"cpp_examples marked_blocks={len(discovered)} compiled={compiled_count} failures={len(failures)}")
    for failure in failures:
        print(f"FAIL {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
