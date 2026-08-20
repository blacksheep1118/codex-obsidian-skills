#!/usr/bin/env python3
"""Shared Notes/Skills lock and compatibility contract helpers."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

CURRENT_VAULT_CONTRACT_VERSION = 1
SKILLS_REPOSITORY = "blacksheep1118/codex-obsidian-skills"
MAINTAINER_SKILL = "solvenotes-vault-maintainer"
LOCK_RELATIVE_PATH = Path(".github/solvenotes-skills.lock.json")
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
FULL_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
PROVENANCE_FILENAME = ".codex-skill-install.json"
PROVENANCE_SCHEMA_VERSION = 1
EXCLUDED_NAMES = {PROVENANCE_FILENAME, ".DS_Store"}
LOCK_MATCH_STATUSES = {
    "EXACT_COMMIT_MATCH",
    "CONTENT_MATCH",
    "CONTRACT_ONLY",
    "MISMATCH",
    "PROVENANCE_MISSING",
}


def lock_path(notes_root: Path) -> Path:
    return notes_root / LOCK_RELATIVE_PATH


def maintainer_root(skills_root: Path) -> Path:
    """Resolve either a source Skills repository or an installed mirror."""

    source = skills_root / "skill" / MAINTAINER_SKILL
    if source.is_dir():
        return source
    return skills_root / MAINTAINER_SKILL


def load_lock(notes_root: Path) -> dict[str, Any]:
    path = lock_path(notes_root)
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"lock file must contain a JSON object: {path}")
    return payload


def validate_lock(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if payload.get("repository") != SKILLS_REPOSITORY:
        issues.append(f"repository must be {SKILLS_REPOSITORY!r}")
    commit = payload.get("commit")
    if not isinstance(commit, str) or not FULL_SHA_RE.fullmatch(commit):
        issues.append("commit must be a lower-case full 40-character SHA")
    if payload.get("maintainer_skill") != MAINTAINER_SKILL:
        issues.append(f"maintainer_skill must be {MAINTAINER_SKILL!r}")
    version = payload.get("contract_version")
    if isinstance(version, bool) or not isinstance(version, int):
        issues.append("contract_version must be an integer")
    elif version != CURRENT_VAULT_CONTRACT_VERSION:
        issues.append(
            "contract_version mismatch: "
            f"expected {CURRENT_VAULT_CONTRACT_VERSION}, got {version}"
        )
    digest = payload.get("content_digest")
    if digest is not None and (not isinstance(digest, str) or not FULL_DIGEST_RE.fullmatch(digest)):
        issues.append("content_digest must be a lower-case 64-character SHA-256 when present")
    return issues


def git_head(skills_root: Path) -> tuple[str | None, str | None]:
    """Return the checkout HEAD, or a diagnostic when no Git metadata exists."""

    try:
        result = subprocess.run(
            ["git", "-C", str(skills_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"cannot read Skills Git HEAD: {exc}"
    if result.returncode:
        detail = result.stderr.strip() or f"git exited {result.returncode}"
        return None, detail
    value = result.stdout.strip()
    if not FULL_SHA_RE.fullmatch(value):
        return None, f"Skills Git HEAD is not a full SHA: {value!r}"
    return value, None


def git_clean(skills_root: Path) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(skills_root), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return not result.stdout.strip() if result.returncode == 0 else None


def skill_contract_version(skills_root: Path) -> int | None:
    path = maintainer_root(skills_root) / "scripts" / "vault_contract.py"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"^CURRENT_VAULT_CONTRACT_VERSION\s*=\s*(\d+)\s*$", text, re.MULTILINE)
    return int(match.group(1)) if match else None


def _managed_records(skill_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not skill_root.is_dir():
        return records
    for path in skill_root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(skill_root)
        if relative.name in EXCLUDED_NAMES or any(
            part in {"__pycache__", ".pytest_cache", ".ruff_cache", "dist", "build"}
            for part in relative.parts
        ):
            continue
        data = path.read_bytes()
        records.append(
            {
                "path": relative.as_posix(),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return sorted(records, key=lambda item: item["path"])


def _records_digest(records: list[dict[str, Any]]) -> str:
    canonical = json.dumps(
        records, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _load_provenance(skill_root: Path) -> tuple[dict[str, Any] | None, str | None]:
    path = skill_root / PROVENANCE_FILENAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, None
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"invalid installed provenance: {path}: {exc}"
    if not isinstance(payload, dict):
        return None, f"installed provenance must be an object: {path}"
    return payload, None


def _installed_provenance(skills_root: Path) -> tuple[dict[str, Any] | None, list[str]]:
    manifest, error = _load_provenance(maintainer_root(skills_root))
    return manifest, [error] if error else []


def _provenance_schema_issues(manifest: dict[str, Any], expected_contract: Any) -> list[str]:
    issues: list[str] = []
    if manifest.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
        issues.append("installed provenance schema_version is unsupported")
    if manifest.get("skill") != MAINTAINER_SKILL:
        issues.append("installed provenance skill does not identify the maintainer Skill")
    if manifest.get("source_repository") != SKILLS_REPOSITORY:
        issues.append("installed provenance source_repository does not match the Skills repository")
    source_commit = manifest.get("source_commit")
    if source_commit is not None and (
        not isinstance(source_commit, str) or not FULL_SHA_RE.fullmatch(source_commit)
    ):
        issues.append("installed provenance source_commit must be null or a full SHA")
    if manifest.get("contract_version") != expected_contract:
        issues.append("installed provenance contract_version does not match the lock")
    digest = manifest.get("content_digest")
    if not isinstance(digest, str) or not FULL_DIGEST_RE.fullmatch(digest):
        issues.append("installed provenance content_digest is missing or invalid")
    if not isinstance(manifest.get("managed_files"), list):
        issues.append("installed provenance managed_files must be a list")
    return issues


def validate_checkout(
    notes_root: Path,
    skills_root: Path,
    *,
    require_git: bool = True,
) -> dict[str, Any]:
    """Validate the Notes lock against a source checkout or installed mirror."""

    issues: list[str] = []
    try:
        payload = load_lock(notes_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "issues": [f"cannot load lock: {exc}"]}
    issues.extend(validate_lock(payload))
    maintainer = maintainer_root(skills_root)
    if not (maintainer / "SKILL.md").is_file():
        issues.append(f"missing installed/source Skill: {maintainer}")
    actual_contract = skill_contract_version(skills_root)
    expected_contract = payload.get("contract_version")
    if actual_contract is None:
        issues.append("maintainer Skill does not expose vault_contract.py")
    elif actual_contract != expected_contract:
        issues.append(
            f"Skill contract mismatch: lock={expected_contract}, Skill={actual_contract}"
        )
    actual_sha, git_error = git_head(skills_root)
    provenance, provenance_issues = _installed_provenance(skills_root)
    issues.extend(provenance_issues)
    expected_sha = payload.get("commit")
    expected_digest = payload.get("content_digest")
    status = "PROVENANCE_MISSING"
    if actual_sha is not None:
        clean = git_clean(skills_root)
        actual_digest = _records_digest(_managed_records(maintainer))
        status = (
            "EXACT_COMMIT_MATCH"
            if actual_sha == expected_sha
            and clean is True
            and (not isinstance(expected_digest, str) or expected_digest == actual_digest)
            else "MISMATCH"
        )
        if actual_sha != expected_sha:
            issues.append(f"Skills SHA mismatch: lock={expected_sha}, checkout={actual_sha}")
        if clean is not True:
            issues.append("Skills source checkout is dirty or its Git status is unavailable")
        if isinstance(expected_digest, str) and expected_digest != actual_digest:
            issues.append(
                f"Skills content digest mismatch: lock={expected_digest}, checkout={actual_digest}"
            )
    elif require_git:
        issues.append(f"Skills checkout has no verifiable Git HEAD: {git_error}")
    if actual_sha is None:
        if provenance is None:
            status = "PROVENANCE_MISSING"
            if not provenance_issues:
                issues.append(
                    f"installed Skills mirror has no {PROVENANCE_FILENAME}; cannot verify source"
                )
        else:
            schema_issues = _provenance_schema_issues(provenance, expected_contract)
            issues.extend(schema_issues)
            source_commit = provenance.get("source_commit")
            actual_digest = _records_digest(_managed_records(maintainer_root(skills_root)))
            manifest_digest = provenance.get("content_digest")
            manifest_records = provenance.get("managed_files")
            if schema_issues:
                status = "MISMATCH"
            elif not isinstance(manifest_records, list) or manifest_records != _managed_records(maintainer_root(skills_root)) or manifest_digest != actual_digest:
                status = "MISMATCH"
                issues.append("installed Skills content digest or managed file list mismatch")
            elif source_commit == expected_sha and isinstance(expected_digest, str) and manifest_digest == expected_digest:
                status = "EXACT_COMMIT_MATCH"
            elif source_commit == expected_sha:
                status = "CONTRACT_ONLY"
                issues.append(
                    "installed provenance names the locked commit, but the lock has no matching content_digest"
                )
            elif isinstance(expected_digest, str) and manifest_digest == expected_digest:
                status = "CONTENT_MATCH"
            elif provenance.get("contract_version") == expected_contract:
                status = "CONTRACT_ONLY"
                issues.append(
                    "installed Skills provenance proves only the contract, not the locked commit"
                )
            else:
                status = "MISMATCH"
                issues.append(
                    f"installed Skills provenance mismatch: lock={expected_sha}, "
                    f"source={source_commit or 'UNAVAILABLE'}"
                )
    if status not in {"EXACT_COMMIT_MATCH", "CONTENT_MATCH"} and not require_git and status == "PROVENANCE_MISSING":
        issues.append("--allow-no-git does not bypass provenance verification")
    return {
        "ok": not issues and status in {"EXACT_COMMIT_MATCH", "CONTENT_MATCH"},
        "issues": issues,
        "lock": payload,
        "actual_sha": actual_sha,
        "actual_contract_version": actual_contract,
        "git_error": git_error,
        "provenance_status": status if status in LOCK_MATCH_STATUSES else "MISMATCH",
        "provenance": provenance,
    }
