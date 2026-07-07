#!/usr/bin/env python3
"""Fail when repository junk files are tracked by Git."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_COMPONENTS = {
    ".DS_Store",
    ".pytest_cache",
    ".ruff_cache",
    "__MACOSX",
    "__pycache__",
    "build",
    "converted_pptx",
    "dist",
    "tmp",
    ".tmp",
    "test-output",
}
FORBIDDEN_SUFFIXES = (".pyc",)
FORBIDDEN_COMPONENT_PREFIXES = ("._",)
FORBIDDEN_COMPONENT_SUFFIXES = (".egg-info",)


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def is_git_repo(root: Path) -> bool:
    result = run_git(root, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == b"true"


def tracked_files(root: Path) -> list[str]:
    result = run_git(root, "ls-files", "-z")
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or "git ls-files failed")
    return [item.decode("utf-8", errors="replace") for item in result.stdout.split(b"\0") if item]


def workspace_files(root: Path) -> list[str]:
    files: list[str] = []
    for path in root.rglob("*"):
        if ".git" in path.parts:
            continue
        if path.is_file():
            files.append(path.relative_to(root).as_posix())
    return sorted(files)


def is_forbidden(path: str) -> bool:
    parts = Path(path).parts
    if any(part in FORBIDDEN_COMPONENTS for part in parts):
        return True
    if any(part.startswith(FORBIDDEN_COMPONENT_PREFIXES) for part in parts):
        return True
    if any(part.endswith(FORBIDDEN_COMPONENT_SUFFIXES) for part in parts):
        return True
    return path.endswith(FORBIDDEN_SUFFIXES)


def report(kind: str, offenders: list[str]) -> None:
    print(f"ERROR: forbidden {kind} files found:", file=sys.stderr)
    for path in offenders:
        print(f"  {path}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root to check")
    args = parser.parse_args()
    root = args.root.resolve()

    if not root.exists():
        print(f"ERROR: root does not exist: {root}", file=sys.stderr)
        return 2

    if is_git_repo(root):
        try:
            paths = tracked_files(root)
        except RuntimeError as exc:
            print(f"ERROR: could not inspect tracked files with git ls-files: {exc}", file=sys.stderr)
            return 2
        offenders = sorted(path for path in paths if is_forbidden(path))
        if offenders:
            print("repo_hygiene failed", file=sys.stderr)
            report("Git-tracked", offenders)
            print("Remove generated files from tracking with git rm --cached, or delete them if they are not useful source files.", file=sys.stderr)
            return 1
        print(f"repo_hygiene ok tracked_files={len(paths)}")
        return 0

    print(f"repo_hygiene warning: {root} is not a Git repository; scanning workspace files only.", file=sys.stderr)
    paths = workspace_files(root)
    offenders = sorted(path for path in paths if is_forbidden(path))
    if offenders:
        print("repo_hygiene failed", file=sys.stderr)
        report("workspace", offenders)
        return 1
    print(f"repo_hygiene ok workspace_files={len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
