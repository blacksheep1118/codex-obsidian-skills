#!/usr/bin/env python3
"""Shared Notes/Skills lock and compatibility contract helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

CURRENT_VAULT_CONTRACT_VERSION = 2
CURRENT_LOCK_SCHEMA_VERSION = 2
SKILLS_REPOSITORY = "blacksheep1118/codex-obsidian-skills"
MAINTAINER_SKILL = "solvenotes-vault-maintainer"
ALGORITHM_JOB_SKILL = "algorithm-job-notes-for-obsidian"
REQUIRED_SKILLS = (MAINTAINER_SKILL, ALGORITHM_JOB_SKILL)
LOCK_RELATIVE_PATH = Path(".github/solvenotes-skills.lock.json")
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
FULL_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
PROVENANCE_FILENAME = ".codex-skill-install.json"
PROVENANCE_SCHEMA_VERSION = 2
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


def skill_root(skills_root: Path, name: str) -> Path:
    """Resolve a Skill in either a source checkout or an installed mirror."""

    source = skills_root / "skill" / name
    return source if source.is_dir() else skills_root / name


def load_lock(notes_root: Path) -> dict[str, Any]:
    override = os.environ.get("SOLVENOTES_SKILLS_LOCK_OVERRIDE")
    path = Path(override).expanduser().absolute() if override else lock_path(notes_root)
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"lock file must contain a JSON object: {path}")
    return payload


def validate_lock(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    schema = payload.get("schema_version")
    if schema != CURRENT_LOCK_SCHEMA_VERSION:
        issues.append(
            "lock schema_version mismatch: "
            f"expected {CURRENT_LOCK_SCHEMA_VERSION}, got {schema!r}; "
            "run update_notes_skill_lock.py to migrate the lock"
        )
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
    skills = payload.get("skills")
    if not isinstance(skills, dict):
        issues.append("skills must be an object containing the required Skill closure")
    else:
        if set(skills) != set(REQUIRED_SKILLS):
            issues.append(
                "skills must contain exactly the required closure: "
                + ", ".join(REQUIRED_SKILLS)
            )
        for name in REQUIRED_SKILLS:
            record = skills.get(name)
            digest = record.get("content_digest") if isinstance(record, dict) else None
            if not isinstance(digest, str) or not FULL_DIGEST_RE.fullmatch(digest):
                issues.append(f"skills.{name}.content_digest must be a lower-case SHA-256")
    graph_digest = payload.get("dependency_graph_digest")
    if not isinstance(graph_digest, str) or not FULL_DIGEST_RE.fullmatch(graph_digest):
        issues.append("dependency_graph_digest must be a lower-case 64-character SHA-256")
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


def skill_content_digest(skills_root: Path, name: str) -> str | None:
    root = skill_root(skills_root, name)
    records = _managed_records(root)
    return _records_digest(records) if records else None


def dependency_graph_digest(graph: dict[str, list[str] | tuple[str, ...]]) -> str:
    canonical_graph = {
        name: sorted(dict.fromkeys(graph.get(name, ())))
        for name in sorted(REQUIRED_SKILLS)
    }
    canonical = json.dumps(
        canonical_graph,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def source_dependency_graph(skills_root: Path) -> dict[str, list[str]] | None:
    path = skills_root / "skill" / "dependencies.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    required = payload.get("required") if isinstance(payload, dict) else None
    if not isinstance(required, dict):
        return None
    graph: dict[str, list[str]] = {}
    for name in REQUIRED_SKILLS:
        values = required.get(name, [])
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            return None
        graph[name] = sorted(dict.fromkeys(values))
    return graph


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


def _installed_provenance(
    skills_root: Path,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    manifests: dict[str, dict[str, Any]] = {}
    issues: list[str] = []
    for name in REQUIRED_SKILLS:
        manifest, error = _load_provenance(skill_root(skills_root, name))
        if error:
            issues.append(error)
        elif manifest is not None:
            manifests[name] = manifest
    return manifests, issues


def _provenance_schema_issues(
    manifest: dict[str, Any], expected_contract: Any, expected_skill: str
) -> list[str]:
    issues: list[str] = []
    if manifest.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
        issues.append("installed provenance schema_version is unsupported")
    if manifest.get("skill") != expected_skill:
        issues.append(f"installed provenance skill does not identify {expected_skill}")
    if manifest.get("source_repository") != SKILLS_REPOSITORY:
        issues.append("installed provenance source_repository does not match the Skills repository")
    source_commit = manifest.get("source_commit")
    if source_commit is not None and (
        not isinstance(source_commit, str) or not FULL_SHA_RE.fullmatch(source_commit)
    ):
        issues.append("installed provenance source_commit must be null or a full SHA")
    if expected_skill == MAINTAINER_SKILL and manifest.get("contract_version") != expected_contract:
        issues.append("installed provenance contract_version does not match the lock")
    if not isinstance(manifest.get("source_dirty"), bool):
        issues.append("installed provenance source_dirty must be a boolean")
    digest = manifest.get("installed_content_digest")
    if not isinstance(digest, str) or not FULL_DIGEST_RE.fullmatch(digest):
        issues.append("installed provenance installed_content_digest is missing or invalid")
    source_digest = manifest.get("source_tree_digest")
    if not isinstance(source_digest, str) or not FULL_DIGEST_RE.fullmatch(source_digest):
        issues.append("installed provenance source_tree_digest is missing or invalid")
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
    for name in REQUIRED_SKILLS:
        root = skill_root(skills_root, name)
        if not (root / "SKILL.md").is_file():
            issues.append(f"missing installed/source Skill: {root}")
    actual_contract = skill_contract_version(skills_root)
    expected_contract = payload.get("contract_version")
    if actual_contract is None:
        issues.append("maintainer Skill does not expose vault_contract.py")
    elif actual_contract != expected_contract:
        issues.append(
            f"Skill contract mismatch: lock={expected_contract}, Skill={actual_contract}"
        )
    actual_sha, git_error = git_head(skills_root)
    provenances, provenance_issues = _installed_provenance(skills_root)
    issues.extend(provenance_issues)
    expected_sha = payload.get("commit")
    expected_skills = payload.get("skills") if isinstance(payload.get("skills"), dict) else {}
    status = "PROVENANCE_MISSING"
    if actual_sha is not None:
        clean = git_clean(skills_root)
        actual_digests = {
            name: skill_content_digest(skills_root, name) for name in REQUIRED_SKILLS
        }
        status = (
            "EXACT_COMMIT_MATCH"
            if actual_sha == expected_sha
            and clean is True
            and all(
                isinstance(expected_skills.get(name), dict)
                and expected_skills[name].get("content_digest") == actual_digests[name]
                for name in REQUIRED_SKILLS
            )
            else "MISMATCH"
        )
        if actual_sha != expected_sha:
            issues.append(f"Skills SHA mismatch: lock={expected_sha}, checkout={actual_sha}")
        if clean is not True:
            issues.append("Skills source checkout is dirty or its Git status is unavailable")
        for name in REQUIRED_SKILLS:
            record = expected_skills.get(name)
            expected_digest = record.get("content_digest") if isinstance(record, dict) else None
            if expected_digest != actual_digests[name]:
                issues.append(
                    f"Skills content digest mismatch for {name}: "
                    f"lock={expected_digest}, checkout={actual_digests[name]}"
                )
        graph = source_dependency_graph(skills_root)
        actual_graph_digest = dependency_graph_digest(graph) if graph is not None else None
        if actual_graph_digest != payload.get("dependency_graph_digest"):
            issues.append("Skills dependency graph digest does not match the lock")
    elif require_git:
        issues.append(f"Skills checkout has no verifiable Git HEAD: {git_error}")
    if actual_sha is None:
        if set(provenances) != set(REQUIRED_SKILLS):
            status = "PROVENANCE_MISSING"
            if not provenance_issues:
                issues.append(
                    "installed Skills mirror is missing provenance for: "
                    + ", ".join(sorted(set(REQUIRED_SKILLS) - set(provenances)))
                )
        else:
            schema_issues: list[str] = []
            exact = True
            content_match = True
            explicit_source_mismatch = False
            for name in REQUIRED_SKILLS:
                provenance = provenances[name]
                schema_issues.extend(
                    _provenance_schema_issues(provenance, expected_contract, name)
                )
                actual_records = _managed_records(skill_root(skills_root, name))
                actual_digest = _records_digest(actual_records)
                expected_record = expected_skills.get(name)
                expected_digest = (
                    expected_record.get("content_digest")
                    if isinstance(expected_record, dict)
                    else None
                )
                if provenance.get("managed_files") != actual_records or provenance.get(
                    "installed_content_digest"
                ) != actual_digest:
                    schema_issues.append(
                        f"installed Skills content digest or managed file list mismatch for {name}"
                    )
                source_commit = provenance.get("source_commit")
                explicit_source_mismatch = explicit_source_mismatch or (
                    source_commit is not None and source_commit != expected_sha
                )
                exact = exact and source_commit == expected_sha and provenance.get("source_dirty") is False
                content_match = content_match and actual_digest == expected_digest
            issues.extend(schema_issues)
            if schema_issues:
                status = "MISMATCH"
            elif explicit_source_mismatch:
                status = "MISMATCH"
                issues.append("installed Skills source_commit does not match the locked commit")
            elif exact and content_match:
                status = "EXACT_COMMIT_MATCH"
            elif content_match:
                status = "CONTENT_MATCH"
            elif provenances[MAINTAINER_SKILL].get("contract_version") == expected_contract:
                status = "CONTRACT_ONLY"
                issues.append(
                    "installed Skills provenance proves only the contract, not the locked dependency closure"
                )
            else:
                status = "MISMATCH"
                issues.append(
                    f"installed Skills provenance mismatch: lock={expected_sha}, "
                    "dependency closure does not match"
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
        "provenance": provenances,
    }
