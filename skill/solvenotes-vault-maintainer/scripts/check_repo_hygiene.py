#!/usr/bin/env python3
"""Check repository-local junk, caches, and Obsidian UI state files."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from notes_utils import ROOT, rel

JUNK_DIR_NAMES = {"__MACOSX", "__pycache__"}
JUNK_FILE_NAMES = {".DS_Store", ".DS_store"}
JUNK_FILE_SUFFIXES = {".pyc"}
OBSIDIAN_WORKSPACE = Path(".obsidian/workspace.json")
OBSIDIAN_GRAPH = Path(".obsidian/graph.json")
GRAPH_UI_KEYS = {
    "centerStrength",
    "close",
    "collapse-color-groups",
    "collapse-display",
    "collapse-filter",
    "collapse-forces",
    "linkDistance",
    "linkStrength",
    "lineSizeMultiplier",
    "nodeSizeMultiplier",
    "repelStrength",
    "scale",
    "showAttachments",
    "showExistingOnly",
    "showOrphans",
    "showTags",
    "textFadeMultiplier",
}


def run_git(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def git_path_set(args: list[str]) -> set[str]:
    result = run_git(args)
    if result.returncode != 0 or not result.stdout:
        return set()
    return {item for item in result.stdout.split("\0") if item}


def tracked_paths() -> set[str]:
    return git_path_set(["ls-files", "-z"])


def staged_paths() -> set[str]:
    return git_path_set(["diff", "--cached", "--name-only", "-z"])


def staged_deletions() -> set[str]:
    result = run_git(["diff", "--cached", "--name-status", "-z"])
    if result.returncode != 0 or not result.stdout:
        return set()
    parts = [item for item in result.stdout.split("\0") if item]
    deleted: set[str] = set()
    i = 0
    while i < len(parts):
        status = parts[i]
        path_index = i + 1
        if status.startswith(("R", "C")):
            path_index = i + 2
        if path_index < len(parts) and status == "D":
            deleted.add(parts[path_index])
        i = path_index + 1
    return deleted


def ignored(path: str) -> bool:
    result = run_git(["check-ignore", "-q", "--", path])
    return result.returncode == 0


def repo_paths() -> Iterable[Path]:
    for path in ROOT.rglob("*"):
        if ".git" in path.relative_to(ROOT).parts:
            continue
        yield path


def is_junk(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    name = path.name
    if path.is_dir() and name in JUNK_DIR_NAMES:
        return True
    if path.is_file() and name in JUNK_FILE_NAMES:
        return True
    if path.is_file() and name.startswith("._"):
        return True
    if path.is_file() and path.suffix in JUNK_FILE_SUFFIXES:
        return True
    return relative == OBSIDIAN_WORKSPACE


def changed_graph_keys() -> list[str]:
    if not (ROOT / OBSIDIAN_GRAPH).exists():
        return []
    result = run_git(["diff", "--unified=0", "--", OBSIDIAN_GRAPH.as_posix()])
    if result.returncode != 0 or not result.stdout.strip():
        return []
    keys: set[str] = set()
    for line in result.stdout.splitlines():
        if not line or line[0] not in "+-":
            continue
        if line.startswith(("+++", "---")):
            continue
        stripped = line[1:].strip()
        if not stripped.startswith('"') or '":' not in stripped:
            continue
        keys.add(stripped.split('":', 1)[0].strip('"'))
    return sorted(keys)


def classify_junk(path: Path, tracked: set[str], staged: set[str], deleted: set[str]) -> dict[str, object]:
    path_rel = rel(path)
    path_ignored = ignored(path_rel)
    staged_for_removal = path_rel in deleted
    state = {
        "path": path_rel,
        "kind": "directory" if path.is_dir() else "file",
        "tracked": path_rel in tracked,
        "staged": path_rel in staged,
        "staged_for_removal": staged_for_removal,
        "ignored": path_ignored,
    }
    state["problem"] = bool((state["tracked"] or state["staged"]) and not staged_for_removal or not path_ignored)
    return state


def build_report() -> dict[str, object]:
    tracked = tracked_paths()
    staged = staged_paths()
    deleted = staged_deletions()
    junk = [classify_junk(path, tracked, staged, deleted) for path in repo_paths() if is_junk(path)]
    graph_path = OBSIDIAN_GRAPH.as_posix()
    graph_keys = changed_graph_keys()
    graph_tracked = graph_path in tracked
    graph_staged = graph_path in staged
    graph_staged_for_removal = graph_path in deleted
    graph_ignored = ignored(graph_path) if (ROOT / OBSIDIAN_GRAPH).exists() else False
    graph_ui_only_dirty = bool(graph_keys) and set(graph_keys).issubset(GRAPH_UI_KEYS)
    graph_problem = (graph_tracked or graph_staged) and not graph_staged_for_removal
    graph_problem = graph_problem or (bool(graph_keys) and graph_ui_only_dirty)
    graph = {
        "path": graph_path,
        "exists": (ROOT / OBSIDIAN_GRAPH).exists(),
        "tracked": graph_tracked,
        "staged": graph_staged,
        "staged_for_removal": graph_staged_for_removal,
        "ignored": graph_ignored,
        "changed_keys": graph_keys,
        "ui_only_dirty": graph_ui_only_dirty,
        "problem": graph_problem,
    }
    problems = [item for item in junk if item["problem"]]
    if graph_problem:
        problems.append({"path": graph_path, "kind": "obsidian_graph_ui_state", "changed_keys": graph_keys})
    return {
        "junk_items": junk,
        "graph": graph,
        "problem_count": len(problems),
        "problems": problems,
    }


def print_human(report: dict[str, object]) -> None:
    junk = report["junk_items"]
    assert isinstance(junk, list)
    print(f"repo_hygiene_junk_items {len(junk)}")
    for item in junk:
        status = "ISSUE" if item["problem"] else "IGNORED"
        print(
            f"{status} {item['path']} tracked={item['tracked']} staged={item['staged']} "
            f"staged_for_removal={item['staged_for_removal']} ignored={item['ignored']}"
        )
    graph = report["graph"]
    assert isinstance(graph, dict)
    print(
        "obsidian_graph "
        f"exists={graph['exists']} tracked={graph['tracked']} staged={graph['staged']} "
        f"staged_for_removal={graph['staged_for_removal']} ignored={graph['ignored']} "
        f"ui_only_dirty={graph['ui_only_dirty']}"
    )
    if graph["changed_keys"]:
        print("obsidian_graph_changed_keys " + ",".join(str(key) for key in graph["changed_keys"]))
    print(f"repo_hygiene_issues {report['problem_count']}")
    for item in report["problems"]:
        print(f"ISSUE {item['path']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    return 1 if report["problem_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
