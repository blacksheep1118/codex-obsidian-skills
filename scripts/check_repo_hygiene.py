#!/usr/bin/env python3
"""Fail when repository junk files are tracked by Git."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True

from install_ignore import should_ignore_relative


ROOT = Path(__file__).resolve().parents[1]


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


def workspace_paths(root: Path) -> list[str]:
    offenders: list[str] = []
    for current_root, dirs, files in os.walk(root):
        current = Path(current_root)
        try:
            relative_root = current.relative_to(root)
        except ValueError:
            continue
        if ".git" in relative_root.parts:
            dirs[:] = []
            continue

        kept_dirs = []
        for dirname in dirs:
            if relative_root == Path(".") and dirname == ".git":
                continue
            relative = relative_root / dirname if relative_root != Path(".") else Path(dirname)
            if is_forbidden(relative.as_posix()):
                offenders.append(relative.as_posix())
            else:
                kept_dirs.append(dirname)
        dirs[:] = kept_dirs

        for filename in files:
            relative = relative_root / filename if relative_root != Path(".") else Path(filename)
            if is_forbidden(relative.as_posix()):
                offenders.append(relative.as_posix())
    return sorted(offenders)


def is_forbidden(path: str) -> bool:
    return should_ignore_relative(Path(path))


def report(kind: str, offenders: list[str]) -> None:
    print(f"ERROR: forbidden {kind} files found:", file=sys.stderr)
    for path in offenders:
        print(f"  {path}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root to check")
    parser.add_argument(
        "--scan-worktree",
        action="store_true",
        help="also scan untracked/ignored workspace artifacts; default checks Git-tracked files only in Git repositories",
    )
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

        if args.scan_worktree:
            workspace_offenders = workspace_paths(root)
            if workspace_offenders:
                print("repo_hygiene failed", file=sys.stderr)
                report("workspace", workspace_offenders)
                print("Delete ignored local artifacts or rerun without --scan-worktree for the Git-tracked check.", file=sys.stderr)
                return 1
            print(f"repo_hygiene ok tracked_files={len(paths)} workspace_scan=clean")
            return 0

        print(f"repo_hygiene ok tracked_files={len(paths)}")
        return 0

    print(f"repo_hygiene warning: {root} is not a Git repository; scanning workspace files only.", file=sys.stderr)
    offenders = workspace_paths(root)
    if offenders:
        print("repo_hygiene failed", file=sys.stderr)
        report("workspace", offenders)
        return 1
    print("repo_hygiene ok workspace_scan=clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
