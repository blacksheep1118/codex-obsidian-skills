"""Shared ignore rules for installing skill folders."""

from __future__ import annotations

from pathlib import Path
import shutil


IGNORED_NAMES = {
    ".DS_Store",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    "__MACOSX",
    "__pycache__",
    "build",
    "converted_pptx",
    "dist",
}
IGNORED_PREFIXES = ("._",)
IGNORED_SUFFIXES = (".pyc", ".egg-info")


def should_ignore_name(name: str) -> bool:
    return name in IGNORED_NAMES or name.startswith(IGNORED_PREFIXES) or name.endswith(IGNORED_SUFFIXES)


def should_ignore_relative(path: Path) -> bool:
    return any(should_ignore_name(part) for part in path.parts)


def ignore_patterns(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if should_ignore_name(name)}


def remove_ignored_artifacts(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), reverse=True):
        relative = path.relative_to(root)
        if not should_ignore_relative(relative):
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
