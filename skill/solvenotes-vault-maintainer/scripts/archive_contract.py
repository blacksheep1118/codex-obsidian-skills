"""Shared deterministic ZIP safety and manifest helpers."""

from __future__ import annotations

import hashlib
import json
import stat
import unicodedata
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
MAX_ARCHIVE_INPUT_BYTES = 1024 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 100_000
MAX_ARCHIVE_MEMBER_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 1000
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
WINDOWS_INVALID_CHARS = frozenset('<>:"|?*')
WINDOWS_RESERVED_NAMES = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{index}" for index in range(1, 10)),
        *(f"lpt{index}" for index in range(1, 10)),
    }
)


def _portable_component(part: str) -> bool:
    if not part or part.endswith((" ", ".")):
        return False
    if any(ord(character) < 32 or ord(character) == 127 for character in part):
        return False
    if any(character in WINDOWS_INVALID_CHARS for character in part):
        return False
    device_stem = part.rstrip(" .").split(".", 1)[0].casefold()
    return device_stem not in WINDOWS_RESERVED_NAMES


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
        and bool(path.parts)
        and path.as_posix() == name
        and not windows_path.is_absolute()
        and not windows_path.drive
        and ".." not in path.parts
        and all(_portable_component(part) for part in path.parts)
        and not any(
            part in forbidden_parts
            or part.startswith("._")
            or part in forbidden_names
            for part in path.parts
        )
    )


def portable_path_collision_issues(names: list[str]) -> list[str]:
    """Report paths that collide on case-insensitive, NFC-normalizing filesystems."""

    seen: dict[str, str] = {}
    issues: list[str] = []
    for name in names:
        key = unicodedata.normalize("NFC", name).casefold()
        previous = seen.get(key)
        if previous is not None and previous != name:
            issues.append(f"portable path collision: {previous!r} and {name!r}")
        else:
            seen[key] = name
    return issues


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


def archive_budget_issues(infos: list[zipfile.ZipInfo]) -> list[str]:
    """Reject archive shapes that could exhaust memory or decompression time."""

    issues: list[str] = []
    if len(infos) > MAX_ARCHIVE_ENTRIES:
        issues.append(f"ZIP entry count exceeds safety limit: {len(infos)}")
        return issues
    total = 0
    for info in infos:
        if info.file_size > MAX_ARCHIVE_MEMBER_BYTES:
            issues.append(f"ZIP entry exceeds uncompressed size limit: {info.filename}")
        total += info.file_size
        if total > MAX_ARCHIVE_TOTAL_UNCOMPRESSED_BYTES:
            issues.append("ZIP total uncompressed size exceeds safety limit")
            break
        if info.file_size and (
            info.compress_size == 0
            or info.file_size > info.compress_size * MAX_ARCHIVE_COMPRESSION_RATIO
        ):
            issues.append(f"ZIP entry exceeds compression-ratio limit: {info.filename}")
    return issues


def read_member_limited(
    archive: zipfile.ZipFile,
    name: str,
    *,
    max_bytes: int = MAX_MANIFEST_BYTES,
) -> bytes:
    """Read one member with a hard decompressed-byte ceiling."""

    with archive.open(name, "r") as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"ZIP member exceeds read limit ({max_bytes} bytes): {name}")
    return data


def member_digest(archive: zipfile.ZipFile, name: str) -> tuple[int, str]:
    """Stream one member once and return its decompressed size and SHA-256."""

    digest = hashlib.sha256()
    size = 0
    with archive.open(name, "r") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_ARCHIVE_MEMBER_BYTES:
                raise ValueError(f"ZIP member exceeds read limit: {name}")
            digest.update(chunk)
    return size, digest.hexdigest()
