"""Deterministic provenance and content digests for installed Skills."""

from __future__ import annotations

import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import subprocess
import tarfile
import tempfile
from typing import Any, Iterable

from install_ignore import should_ignore_relative
from shared.skill_metadata import SKILL_NAME_RE


PROVENANCE_FILENAME = ".codex-skill-install.json"
PROVENANCE_SCHEMA_VERSION = 2
INSTALL_EXCLUDED_PARTS = {"tests"}
HEX_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def _managed_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    if root.is_symlink():
        raise ValueError(f"provenance root must not be a symlink: {root}")
    if not root.is_dir():
        return paths
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"provenance payload must not contain symlinks: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if (
            relative.name == PROVENANCE_FILENAME
            or should_ignore_relative(relative)
            or any(part in INSTALL_EXCLUDED_PARTS for part in relative.parts)
        ):
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


def _safe_manifest_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def validate_provenance_payload(
    payload: dict[str, Any],
    *,
    expected_skill: str | None = None,
    expected_repository: str | None = None,
) -> list[str]:
    """Return schema issues without trusting any manifest field."""

    issues: list[str] = []
    if payload.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
        issues.append("unsupported provenance schema")
    skill = payload.get("skill")
    if not isinstance(skill, str) or not SKILL_NAME_RE.fullmatch(skill):
        issues.append("provenance skill must be a canonical lowercase Skill name")
    elif expected_skill is not None and skill != expected_skill:
        issues.append(f"provenance skill does not match {expected_skill!r}")
    repository = payload.get("source_repository")
    if not isinstance(repository, str) or not repository or any(char.isspace() for char in repository):
        issues.append("source_repository must be a non-empty repository identifier")
    elif expected_repository is not None and repository != expected_repository:
        issues.append(f"source_repository does not match {expected_repository!r}")
    commit = payload.get("source_commit")
    if commit is not None and (not isinstance(commit, str) or not GIT_COMMIT_RE.fullmatch(commit)):
        issues.append("source_commit must be null or a full lowercase 40-character Git SHA")
    dirty = payload.get("source_dirty")
    if dirty is not None and not isinstance(dirty, bool):
        issues.append("source_dirty must be boolean or null")
    if dirty is not None and commit is None:
        issues.append("source_commit is required when source_dirty is known")
    for field in ("source_tree_digest", "installed_content_digest", "content_digest"):
        value = payload.get(field)
        if not isinstance(value, str) or not HEX_DIGEST_RE.fullmatch(value):
            issues.append(f"{field} must be a lowercase SHA-256 digest")
    source_digest = payload.get("source_tree_digest")
    installed_digest = payload.get("installed_content_digest")
    compatibility_digest = payload.get("content_digest")
    if (
        isinstance(source_digest, str)
        and isinstance(installed_digest, str)
        and HEX_DIGEST_RE.fullmatch(source_digest)
        and HEX_DIGEST_RE.fullmatch(installed_digest)
        and source_digest != installed_digest
    ):
        issues.append("source_tree_digest must match installed_content_digest")
    if (
        isinstance(compatibility_digest, str)
        and isinstance(installed_digest, str)
        and HEX_DIGEST_RE.fullmatch(compatibility_digest)
        and HEX_DIGEST_RE.fullmatch(installed_digest)
        and compatibility_digest != installed_digest
    ):
        issues.append("content_digest must match installed_content_digest")
    contract = payload.get("contract_version")
    if contract is not None and (
        not isinstance(contract, int) or isinstance(contract, bool) or contract < 1
    ):
        issues.append("contract_version must be a positive integer or null")

    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, list) or any(
        not isinstance(item, str) or not SKILL_NAME_RE.fullmatch(item)
        for item in dependencies
    ):
        issues.append("dependencies must be a list of canonical lowercase Skill names")
        valid_dependencies: list[str] = []
    else:
        valid_dependencies = dependencies
        if dependencies != sorted(set(dependencies)):
            issues.append("dependencies must be sorted and unique")
        if isinstance(skill, str) and skill in dependencies:
            issues.append("a Skill cannot depend on itself")

    dependency_digests = payload.get("dependency_digests")
    if not isinstance(dependency_digests, dict):
        issues.append("dependency_digests must be an object")
    else:
        if set(dependency_digests) != set(valid_dependencies):
            issues.append("dependency_digests keys must exactly match dependencies")
        for dependency, digest in dependency_digests.items():
            if not isinstance(dependency, str) or not isinstance(digest, str) or not HEX_DIGEST_RE.fullmatch(digest):
                issues.append(f"dependency digest for {dependency!r} must be a lowercase SHA-256 digest")

    managed_files = payload.get("managed_files")
    if not isinstance(managed_files, list):
        issues.append("managed_files must be a list")
    else:
        paths: list[str] = []
        for index, record in enumerate(managed_files):
            if not isinstance(record, dict):
                issues.append(f"managed_files[{index}] must be an object")
                continue
            path = record.get("path")
            size = record.get("size")
            digest = record.get("sha256")
            if not _safe_manifest_path(path):
                issues.append(f"managed_files[{index}].path is not a safe relative path")
            else:
                paths.append(path)
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                issues.append(f"managed_files[{index}].size must be a non-negative integer")
            if not isinstance(digest, str) or not HEX_DIGEST_RE.fullmatch(digest):
                issues.append(f"managed_files[{index}].sha256 must be a lowercase SHA-256 digest")
        if paths != sorted(set(paths)):
            issues.append("managed_files paths must be sorted and unique")
    return issues


def committed_skill_digest(
    repository_root: Path,
    *,
    commit: str,
    skill_name: str,
) -> str | None:
    """Digest one Skill exactly as stored in a reachable Git commit."""

    try:
        result = subprocess.run(
            ["git", "-C", str(repository_root), "archive", "--format=tar", commit, f"skill/{skill_name}"],
            capture_output=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode:
        return None
    prefix = PurePosixPath("skill") / skill_name
    records: list[dict[str, Any]] = []
    try:
        with tarfile.open(fileobj=BytesIO(result.stdout), mode="r:") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                relative = PurePosixPath(member.name).relative_to(prefix)
                path = Path(relative.as_posix())
                if (
                    should_ignore_relative(path)
                    or any(part in INSTALL_EXCLUDED_PARTS for part in path.parts)
                    or path.name == PROVENANCE_FILENAME
                ):
                    continue
                stream = archive.extractfile(member)
                if stream is None:
                    return None
                data = stream.read()
                records.append(
                    {
                        "path": relative.as_posix(),
                        "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                )
    except (KeyError, tarfile.TarError, ValueError):
        return None
    records.sort(key=lambda record: record["path"])
    return content_digest(records)


def source_state(repository_root: Path) -> tuple[str | None, bool | None]:
    """Return the repository HEAD and dirty state as two independent facts."""

    try:
        status = subprocess.run(
            ["git", "-C", str(repository_root), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        result = subprocess.run(
            ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None, None
    value = result.stdout.strip()
    commit = value if result.returncode == 0 and len(value) == 40 else None
    dirty = bool(status.stdout.strip()) if status.returncode == 0 else None
    return commit, dirty


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
    source_root: Path,
    *,
    installed_root: Path | None = None,
    repository_root: Path | None = None,
    skill_name: str,
    repository: str,
    dependencies: Iterable[str] = (),
    dependency_digests: dict[str, str] | None = None,
) -> dict[str, Any]:
    installed_root = installed_root or source_root
    repository_root = repository_root or source_root.parents[1]
    source_records = file_records(source_root)
    installed_records = file_records(installed_root)
    commit, dirty = source_state(repository_root)
    installed_digest = content_digest(installed_records)
    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "skill": skill_name,
        "source_repository": repository,
        "source_commit": commit,
        "source_dirty": dirty,
        "source_tree_digest": content_digest(source_records),
        "installed_content_digest": installed_digest,
        # Kept as a compatibility alias for older external readers. New lock
        # verification uses installed_content_digest explicitly.
        "content_digest": installed_digest,
        "contract_version": _contract_version(source_root),
        "dependencies": sorted(set(dependencies)),
        "dependency_digests": dict(sorted((dependency_digests or {}).items())),
        "managed_files": installed_records,
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
