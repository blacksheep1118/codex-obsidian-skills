"""Shared deterministic ZIP safety and manifest helpers."""

from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import PurePosixPath, PureWindowsPath

COMMON_FORBIDDEN_PARTS = {
    ".git",
    "__MACOSX",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
}
COMMON_FORBIDDEN_NAMES = {"workspace.json", "graph.json", ".DS_Store"}


def safe_entry(
    name: str,
    *,
    forbidden_parts: set[str] | frozenset[str] = frozenset(COMMON_FORBIDDEN_PARTS),
    forbidden_names: set[str] | frozenset[str] = frozenset(COMMON_FORBIDDEN_NAMES),
) -> bool:
    path = PurePosixPath(name)
    windows_path = PureWindowsPath(name)
    return (
        bool(name)
        and "\\" not in name
        and not path.is_absolute()
        and not windows_path.is_absolute()
        and not windows_path.drive
        and ".." not in path.parts
        and not any(
            part in forbidden_parts
            or part.startswith("._")
            or part in forbidden_names
            for part in path.parts
        )
    )


def is_symlink_entry(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return bool(mode and stat.S_ISLNK(mode))


def records_digest(records: list[dict[str, object]]) -> str:
    canonical = json.dumps(
        records,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
