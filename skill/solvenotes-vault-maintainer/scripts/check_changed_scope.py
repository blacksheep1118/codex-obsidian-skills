#!/usr/bin/env python3
"""Report the course scope affected by recent changes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from notes_utils import ROOT


def changed_files(base: str) -> list[str]:
    commands = [
        ["git", "diff", "--name-only", "--diff-filter=ACMRT", f"{base}...HEAD"],
        ["git", "diff", "--name-only", "--diff-filter=ACMRT", "--cached"],
        ["git", "diff", "--name-only", "--diff-filter=ACMRT"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    files: set[str] = set()
    for cmd in commands:
        result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=30)
        if result.returncode == 0:
            files.update(line for line in result.stdout.splitlines() if line.strip())
    return sorted(files)


def course_for(path: str) -> str:
    parts = Path(path).parts
    if not parts:
        return "unknown"
    if len(parts) == 1:
        return "全仓"
    if parts[0] in {".github", "scripts", "agent"}:
        return parts[0]
    return parts[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    files = changed_files(args.base)
    courses = sorted({course_for(path) for path in files if path.endswith(".md")})
    suggested = [
        "python3 scripts/check_links.py",
        "python3 scripts/check_examples.py",
        "python3 scripts/check_source_coverage.py",
    ]
    if any(path.startswith("scripts/") for path in files):
        suggested.append("python3 -m py_compile scripts/*.py")
    if any(path.endswith("source_manifest.md") for path in files):
        suggested.append("python3 scripts/check_source_files.py --strict")

    payload = {
        "base": args.base,
        "changed_files": files,
        "changed_file_count": len(files),
        "affected_courses": courses,
        "suggested_checks": suggested,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"base {args.base}")
        print(f"changed_file_count {len(files)}")
        for course in courses:
            print(f"COURSE {course}")
        for check in suggested:
            print(f"CHECK {check}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
