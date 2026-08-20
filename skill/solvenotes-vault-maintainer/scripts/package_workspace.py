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
import zipfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from safe_io import (
        atomic_binary_writer,
        ensure_safe_input_directory,
        ensure_safe_input_file,
        ensure_safe_output_path,
    )
except ImportError:  # pragma: no cover - source checkout convenience
    from .safe_io import (
        atomic_binary_writer,
        ensure_safe_input_directory,
        ensure_safe_input_file,
        ensure_safe_output_path,
    )

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
MINIMUM_ZIP_EPOCH = 315532800


def safe_root(raw: Path) -> Path:
    root = Path(os.path.abspath(os.fspath(raw.expanduser())))
    try:
        return ensure_safe_input_directory(root)
    except (OSError, ValueError) as exc:
        raise ValueError(f"workspace root must be a real directory without symlink components: {root}") from exc


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
    excluded_lexical = {Path(os.path.abspath(os.fspath(path))) for path in excluded_paths}
    for current_root, directory_names, file_names in os.walk(root, followlinks=False):
        current = Path(current_root)
        kept_directories: list[str] = []
        for name in sorted(directory_names):
            relative = (current / name).relative_to(root)
            candidate = current / name
            if excluded(relative):
                continue
            if candidate.is_symlink():
                raise ValueError(f"workspace contains a symlink directory: {relative}")
            kept_directories.append(name)
        directory_names[:] = kept_directories
        for name in sorted(file_names):
            path = current / name
            relative = path.relative_to(root)
            if relative.parts and relative.parts[0] not in WORKSPACE_TOP_LEVEL and relative != Path("AGENT.md"):
                continue
            if excluded(relative):
                continue
            if path.is_symlink():
                raise ValueError(f"workspace contains a symlink file: {relative}")
            if Path(os.path.abspath(os.fspath(path))) in excluded_lexical:
                continue
            safe_path = ensure_safe_input_file(path)
            data = safe_path.read_bytes()
            entries.append((relative, data, safe_path.stat().st_mode))
    return sorted(entries, key=lambda item: item[0].as_posix())


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


def git_is_clean(path: Path) -> bool | None:
    if not (path / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "status", "--porcelain", "--untracked-files=all"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return not result.stdout.strip()


def skill_content_digest(skills_root: Path) -> str | None:
    maintainer = skills_root / "skill" / "solvenotes-vault-maintainer"
    if not maintainer.is_dir():
        return None
    records: list[dict[str, object]] = []
    for path in sorted(maintainer.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(maintainer)
        if any(part in {"__pycache__", ".pytest_cache", ".ruff_cache", "build", "dist"} for part in relative.parts):
            continue
        if relative.name in {".codex-skill-install.json", ".DS_Store"}:
            continue
        data = ensure_safe_input_file(path).read_bytes()
        records.append(
            {
                "path": relative.as_posix(),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    canonical = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def lock_metadata(notes_root: Path, skills_root: Path, *, allow_lock_drift: bool = False) -> dict[str, object]:
    lock_path = notes_root / ".github" / "solvenotes-skills.lock.json"
    if not lock_path.is_file():
        return {"notes_locked_skills_commit": None, "contract_version": None, "coherent_workspace": False}
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid Notes Skills lock: {lock_path}: {exc}") from exc
    commit = payload.get("commit")
    contract = payload.get("contract_version")
    actual = git_commit(skills_root)
    clean = git_is_clean(skills_root)
    actual_digest = skill_content_digest(skills_root)
    expected_digest = payload.get("content_digest")
    coherent = (
        isinstance(commit, str)
        and isinstance(actual, str)
        and commit == actual
        and clean is True
        and (not isinstance(expected_digest, str) or expected_digest == actual_digest)
    )
    if not coherent and not allow_lock_drift:
        raise ValueError(
            f"Notes lock drift: lock={commit or 'MISSING'}, Skills checkout={actual or 'UNAVAILABLE'}; "
            "use --allow-lock-drift only for a diagnostic package"
        )
    result = {
        "notes_locked_skills_commit": commit if isinstance(commit, str) else None,
        "contract_version": contract if isinstance(contract, int) else None,
        "coherent_workspace": coherent,
        "skills_clean": clean,
        "skills_content_digest": actual_digest,
    }
    if not coherent:
        result["lock_drift"] = {
            "locked": commit,
            "skills_commit": actual,
            "skills_clean": clean,
            "locked_content_digest": expected_digest,
            "skills_content_digest": actual_digest,
        }
    return result


def _file_records(entries: list[tuple[Path, bytes, int]]) -> list[dict[str, object]]:
    return [
        {"path": relative.as_posix(), "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for relative, data, _mode in entries
    ]


def _content_digest(files: list[dict[str, object]]) -> str:
    canonical = json.dumps(files, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def deterministic_epoch(root: Path) -> int:
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    if raw is not None:
        try:
            return max(int(raw), MINIMUM_ZIP_EPOCH)
        except ValueError as exc:
            raise ValueError(f"invalid SOURCE_DATE_EPOCH: {raw}") from exc
    candidates: list[int] = []
    for repository in (root / "notes", root / "skills"):
        if not (repository / ".git").exists():
            continue
        try:
            result = subprocess.run(
                ["git", "-C", str(repository), "show", "-s", "--format=%ct", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                timeout=15,
            )
            candidates.append(int(result.stdout.strip()))
        except (OSError, ValueError, subprocess.SubprocessError):
            continue
    return max(candidates, default=MINIMUM_ZIP_EPOCH)


def manifest_for(root: Path, entries: list[tuple[Path, bytes, int]], *, lock: dict[str, object], epoch: int) -> dict[str, object]:
    generated = datetime.fromtimestamp(epoch, tz=timezone.utc)
    notes_root = root / "notes"
    skills_root = root / "skills"
    files = _file_records(entries)
    return {
        "schema_version": 2,
        "generated_at": generated.isoformat().replace("+00:00", "Z"),
        "workspace_commit": git_commit(root),
        "notes_commit": git_commit(notes_root),
        "skills_commit": git_commit(skills_root),
        **lock,
        "notes_file_count": sum(1 for item in files if item["path"] == "AGENT.md" or str(item["path"]).startswith("notes/")),
        "skills_file_count": sum(1 for item in files if str(item["path"]).startswith("skills/")),
        "file_count": len(files),
        "archive_entry_count": len(files) + 1,
        "content_digest": _content_digest(files),
        "archive_sha256": None,
        "files": files,
    }


def archive_timestamp(epoch: int) -> tuple[int, int, int, int, int, int]:
    epoch = max(epoch, MINIMUM_ZIP_EPOCH)
    value = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return (value.year, value.month, value.day, value.hour, value.minute, value.second)


def write_archive(output: Path, entries: list[tuple[Path, bytes, int]], manifest_bytes: bytes, epoch: int) -> None:
    safe_output = ensure_safe_output_path(Path(os.path.abspath(os.fspath(output))), create_parent=True)
    timestamp = archive_timestamp(epoch)
    with atomic_binary_writer(safe_output) as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for relative, data, mode in entries:
                info = zipfile.ZipInfo(relative.as_posix(), date_time=timestamp)
                info.create_system = 3
                info.external_attr = (0o100755 if mode & 0o111 else 0o100644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
            info = zipfile.ZipInfo("BUILD-MANIFEST.json", date_time=timestamp)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, manifest_bytes)


def write_manifest(path: Path, data: bytes) -> None:
    safe_path = ensure_safe_output_path(Path(os.path.abspath(os.fspath(path))), create_parent=True)
    with atomic_binary_writer(safe_path) as stream:
        stream.write(data)


def package(root: Path, output: Path, manifest_output: Path, *, allow_lock_drift: bool = False) -> tuple[int, int]:
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
    lock = lock_metadata(root / "notes", root / "skills", allow_lock_drift=allow_lock_drift)
    epoch = deterministic_epoch(root)
    manifest = manifest_for(root, entries, lock=lock, epoch=epoch)
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_archive(output, entries, manifest_bytes, epoch)
    archive_sha256 = hashlib.sha256(output.read_bytes()).hexdigest()
    sidecar = dict(manifest)
    sidecar["archive_sha256"] = archive_sha256
    write_manifest(manifest_output, (json.dumps(sidecar, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return len(entries), output.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True, help="Solvenotes workspace root")
    parser.add_argument("--output", type=Path, required=True, help="workspace ZIP outside the root")
    parser.add_argument("--manifest-output", type=Path, required=True, help="sidecar manifest outside the root")
    parser.add_argument("--allow-lock-drift", action="store_true", help="create a diagnostic, non-coherent package")
    args = parser.parse_args()
    count, size = package(args.root, args.output, args.manifest_output, allow_lock_drift=args.allow_lock_drift)
    print(f"workspace_package_path {args.output.expanduser().absolute()}")
    print(f"workspace_package_files {count}")
    print(f"workspace_package_size_bytes {size}")
    print(f"workspace_manifest_path {args.manifest_output.expanduser().absolute()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
