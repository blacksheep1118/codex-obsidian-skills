#!/usr/bin/env python3
"""Report the course scope affected by recent changes."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from notes_utils import ROOT

CHECK_REGISTRY = {
    "links": {"owner": "maintainer", "script": "scripts/check_links.py", "arguments": []},
    "frontmatter": {"owner": "maintainer", "script": "scripts/check_frontmatter.py", "arguments": []},
    "source_manifest": {"owner": "maintainer", "script": "scripts/normalize_source_manifests.py", "arguments": ["--check"]},
    "algorithm_job": {"owner": "maintainer", "script": "scripts/check_algorithm_job_notes.py", "arguments": []},
    "cpp17": {"owner": "algorithm-job", "script": "scripts/check_cpp_examples.py", "arguments": ["--root", "${SOLVENOTES_VAULT_ROOT}"]},
    "naturalness": {"owner": "maintainer", "script": "scripts/check_naturalness.py", "arguments": ["--strict"]},
    "package": {"owner": "maintainer", "script": "scripts/package_vault.py", "arguments": ["--root", "${SOLVENOTES_VAULT_ROOT}"]},
}


def _git_lines(command: list[str], *, allow_failure: bool = False) -> list[str]:
    is_path_listing = "--name-only" in command or "--others" in command
    if is_path_listing:
        # Git's default core.quotePath escapes non-ASCII filenames on macOS.
        # NUL-delimited output preserves Chinese names and names containing
        # whitespace/newlines without making the scope classifier guess.
        command = [command[0], "-c", "core.quotePath=false", *command[1:], "-z"]
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"Git path query failed: {exc}") from exc
        if result.returncode:
            if allow_failure:
                return []
            detail = result.stderr.decode("utf-8", "replace").strip() or f"git exited {result.returncode}"
            raise RuntimeError(f"Git path query failed: {detail}")
        return [
            item.decode("utf-8", errors="surrogateescape")
            for item in result.stdout.split(b"\0")
            if item
        ]
    try:
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Git query failed: {exc}") from exc
    if result.returncode:
        if allow_failure:
            return []
        detail = result.stderr.strip() or f"git exited {result.returncode}"
        raise RuntimeError(f"Git query failed: {detail}")
    return [line for line in result.stdout.splitlines() if line.strip()]


def changed_files(base: str | None, head: str | None) -> list[str]:
    head = head or "HEAD"
    base = base or ""
    commands = [
        ["git", "diff", "--name-only", "--diff-filter=ACDMRT", f"{base}...{head}"] if base else [],
        ["git", "diff", "--name-only", "--diff-filter=ACDMRT", "--cached"],
        ["git", "diff", "--name-only", "--diff-filter=ACDMRT"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    files: set[str] = set()
    for cmd in commands:
        if cmd:
            files.update(_git_lines(cmd))
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


def resolve_range(base: str | None, head: str | None, merge_base: str | None) -> tuple[str | None, str]:
    event = os.environ.get("GITHUB_EVENT_NAME", "").strip()
    resolved_head = head or os.environ.get("GITHUB_SHA") or "HEAD"
    resolved_base = base
    if not resolved_base and event == "pull_request":
        resolved_base = os.environ.get("GITHUB_BASE_SHA")
    if not resolved_base and event == "push":
        before = os.environ.get("GITHUB_EVENT_BEFORE") or os.environ.get("GITHUB_BEFORE")
        if before and set(before) != {"0"}:
            resolved_base = before
    if merge_base:
        candidate = _git_lines(["git", "merge-base", merge_base, resolved_head])
        if candidate:
            resolved_base = candidate[0]
    if not resolved_base:
        candidates = _git_lines(
            ["git", "show-ref", "--verify", "refs/remotes/origin/main"],
            allow_failure=True,
        )
        if candidates:
            resolved_base = "origin/main"
    return resolved_base, resolved_head


def suggested_checks(files: list[str]) -> list[str]:
    checks = {"links", "frontmatter"} if files else set()
    for path in files:
        if path.endswith("source_manifest.md"):
            checks.add("source_manifest")
        if path.startswith("算法岗学习笔记/"):
            checks.update({"algorithm_job", "cpp17"})
        if "runnable" in path.lower() or path.endswith(".cpp"):
            checks.add("cpp17")
        if path.endswith(".md") and ("学习路径" in path or "算法岗" in path):
            checks.add("naturalness")
        if path in {".gitignore", ".gitattributes", "notes.base"} or path.startswith(".github/"):
            checks.add("package")
    return sorted(checks)


def command_records(checks: list[str]) -> list[dict[str, object]]:
    return [{"id": check, **CHECK_REGISTRY[check]} for check in checks]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", help="deprecated alias for --base-sha")
    parser.add_argument("--base-sha")
    parser.add_argument("--head-sha")
    parser.add_argument("--merge-base", help="ref to use when deriving a merge base")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    if args.base and args.base_sha:
        parser.error("--base and --base-sha are mutually exclusive")
    base, head = resolve_range(args.base_sha or args.base, args.head_sha, args.merge_base)
    try:
        files = changed_files(base, head)
    except RuntimeError as exc:
        parser.error(str(exc))
    courses = sorted({course_for(path) for path in files if path.endswith(".md")})
    suggested = suggested_checks(files)

    payload = {
        "base": base,
        "head": head,
        "merge_base": args.merge_base,
        "changed_files": files,
        "changed_file_count": len(files),
        "affected_courses": courses,
        "suggested_checks": suggested,
        "suggested_commands": command_records(suggested),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"base {base or 'UNSET'}")
        print(f"head {head}")
        print(f"changed_file_count {len(files)}")
        for course in courses:
            print(f"COURSE {course}")
        for check in suggested:
            print(f"CHECK {check}")
            record = CHECK_REGISTRY[check]
            arguments = " ".join(str(item) for item in record["arguments"])
            print(
                f"COMMAND {check} owner={record['owner']} script={record['script']}"
                + (f" args={arguments}" if arguments else "")
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
