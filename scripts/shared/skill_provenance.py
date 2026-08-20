"""Deterministic provenance and content digests for installed Skills."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Iterable

from install_ignore import should_ignore_relative


PROVENANCE_FILENAME = ".codex-skill-install.json"
PROVENANCE_SCHEMA_VERSION = 1


def _managed_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    if not root.is_dir():
        return paths
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if relative.name == PROVENANCE_FILENAME or should_ignore_relative(relative):
            continue
        paths.append(relative)
    return sorted(paths, key=lambda value: value.as_posix())


def file_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for relative in _managed_paths(root):
        data = (root / relative).read_bytes()
        records.append(
            {
                "path": relative.as_posix(),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return records


def content_digest(records: Iterable[dict[str, Any]]) -> str:
    canonical = json.dumps(
        list(records), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def source_commit(repository_root: Path) -> str | None:
    try:
        status = subprocess.run(
            ["git", "-C", str(repository_root), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if status.returncode != 0 or status.stdout.strip():
            return None
        result = subprocess.run(
            ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and len(value) == 40 else None


def _contract_version(skill_root: Path) -> int | None:
    path = skill_root / "scripts" / "vault_contract.py"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("CURRENT_VAULT_CONTRACT_VERSION = "):
            try:
                return int(line.split("=", 1)[1].strip())
            except ValueError:
                return None
    return None


def build_provenance(
    skill_root: Path,
    *,
    skill_name: str,
    repository: str,
    dependencies: Iterable[str] = (),
) -> dict[str, Any]:
    records = file_records(skill_root)
    repository_root = skill_root.parents[1]
    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "skill": skill_name,
        "source_repository": repository,
        "source_commit": source_commit(repository_root),
        "contract_version": _contract_version(skill_root),
        "dependencies": sorted(set(dependencies)),
        "content_digest": content_digest(records),
        "managed_files": records,
    }


def write_provenance(skill_root: Path, payload: dict[str, Any]) -> None:
    destination = skill_root / PROVENANCE_FILENAME
    if destination.is_symlink():
        raise ValueError(f"refusing to replace provenance symlink: {destination}")
    rendered = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    fd, temporary_name = tempfile.mkstemp(prefix=f".{PROVENANCE_FILENAME}.", dir=skill_root)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def load_provenance(skill_root: Path) -> dict[str, Any] | None:
    path = skill_root / PROVENANCE_FILENAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid installed Skill provenance: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"installed Skill provenance must be an object: {path}")
    return payload
