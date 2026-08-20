#!/usr/bin/env python3
"""Create a clean, non-secret diagnostic package for the Solvenotes workspace.

This package is for maintainers and model-assisted diagnosis, not for the
Obsidian vault's normal export.  It deliberately excludes Git history,
machine-local Obsidian state, caches, archives, and local configuration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".venv",
    "__pycache__",
    "__MACOSX",
    "build",
    "dist",
    "node_modules",
}
EXCLUDED_NAMES = {
    ".DS_Store",
    "workspace.json",
    "graph.json",
    "BUILD-MANIFEST.json",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".zip"}
WORKSPACE_TOP_LEVEL = {"agent", "notes", "skills"}


def safe_root(raw: Path) -> Path:
    root = raw.expanduser().absolute()
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"workspace root must be a real directory: {root}")
    return root


def excluded(relative: Path) -> bool:
    parts = relative.parts
    if not parts:
        return True
    if any(part in EXCLUDED_DIRS for part in parts):
        return True
    name = relative.name
    if name.startswith("._") or name in EXCLUDED_NAMES:
        return True
    if name.startswith(".env") or name.startswith("workspace.local"):
        return True
    return relative.suffix.lower() in EXCLUDED_SUFFIXES


def inventory(root: Path, excluded_paths: set[Path]) -> list[tuple[Path, bytes, int]]:
    entries: list[tuple[Path, bytes, int]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] not in WORKSPACE_TOP_LEVEL and relative != Path("AGENT.md"):
            continue
        if excluded(relative) or path in excluded_paths:
            continue
        data = path.read_bytes()
        entries.append((relative, data, path.stat().st_mode))
    return entries


def git_commit(path: Path) -> str | None:
    if not (path / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = result.stdout.strip()
    return commit if len(commit) == 40 else None


def lock_metadata(notes_root: Path) -> dict[str, object]:
    lock_path = notes_root / ".github" / "solvenotes-skills.lock.json"
    if not lock_path.is_file():
        return {"skills_lock": None, "contract_version": None}
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"skills_lock": "invalid", "contract_version": None}
    commit = payload.get("commit")
    contract = payload.get("contract_version")
    return {
        "skills_lock": commit if isinstance(commit, str) else "invalid",
        "contract_version": contract if isinstance(contract, int) else None,
    }


def manifest_for(root: Path, entries: list[tuple[Path, bytes, int]]) -> dict[str, object]:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is not None:
        try:
            generated = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
        except (ValueError, OSError, OverflowError) as exc:
            raise ValueError(f"invalid SOURCE_DATE_EPOCH: {epoch}") from exc
    else:
        generated = datetime.now(timezone.utc)
    notes_root = root / "notes"
    skills_root = root / "skills"
    files = [
        {
            "path": relative.as_posix(),
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        for relative, data, _mode in entries
    ]
    return {
        "schema": 1,
        "generated_at": generated.isoformat().replace("+00:00", "Z"),
        "workspace_commit": git_commit(root),
        "notes_commit": git_commit(notes_root),
        "skills_commit": git_commit(skills_root),
        **lock_metadata(notes_root),
        "file_count": len(files),
        "archive_entry_count": len(files) + 1,
        "files": files,
    }


def archive_timestamp() -> tuple[int, int, int, int, int, int]:
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "315532800"))
    value = datetime.fromtimestamp(max(epoch, 315532800), tz=timezone.utc)
    return (value.year, value.month, value.day, value.hour, value.minute, value.second)


def write_archive(output: Path, entries: list[tuple[Path, bytes, int]], manifest_bytes: bytes) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.is_symlink():
        raise ValueError(f"refusing to replace symlink output: {output}")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        timestamp = archive_timestamp()
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for relative, data, mode in entries:
                info = zipfile.ZipInfo(relative.as_posix(), date_time=timestamp)
                info.create_system = 3
                info.external_attr = (mode & 0xFFFF) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
            info = zipfile.ZipInfo("BUILD-MANIFEST.json", date_time=timestamp)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, manifest_bytes)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def write_manifest(path: Path, data: bytes) -> None:
    if path.exists() and path.is_symlink():
        raise ValueError(f"refusing to replace symlink manifest: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def package(root: Path, output: Path, manifest_output: Path) -> tuple[int, int]:
    root = safe_root(root)
    output = output.expanduser().absolute()
    manifest_output = manifest_output.expanduser().absolute()
    for candidate in (output, manifest_output):
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        raise ValueError(f"output must be outside the workspace root: {candidate}")
    if output == manifest_output:
        raise ValueError("ZIP output and manifest output must be different files")
    excluded_paths = {output, manifest_output}
    entries = inventory(root, excluded_paths)
    manifest = manifest_for(root, entries)
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    write_archive(output, entries, manifest_bytes)
    write_manifest(manifest_output, manifest_bytes)
    return len(entries), output.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True, help="Solvenotes workspace root")
    parser.add_argument("--output", type=Path, required=True, help="workspace ZIP outside the root")
    parser.add_argument("--manifest-output", type=Path, required=True, help="sidecar manifest outside the root")
    args = parser.parse_args()
    count, size = package(args.root, args.output, args.manifest_output)
    print(f"workspace_package_path {args.output.expanduser().absolute()}")
    print(f"workspace_package_files {count}")
    print(f"workspace_package_size_bytes {size}")
    print(f"workspace_manifest_path {args.manifest_output.expanduser().absolute()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
