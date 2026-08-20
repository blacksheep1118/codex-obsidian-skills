#!/usr/bin/env python3
"""Shared Notes/Skills lock and compatibility contract helpers."""

from __future__ import annotations

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


def skill_contract_version(skills_root: Path) -> int | None:
    path = maintainer_root(skills_root) / "scripts" / "vault_contract.py"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"^CURRENT_VAULT_CONTRACT_VERSION\s*=\s*(\d+)\s*$", text, re.MULTILINE)
    return int(match.group(1)) if match else None


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
    if actual_sha is None:
        if require_git:
            issues.append(f"Skills checkout has no verifiable Git HEAD: {git_error}")
    elif actual_sha != payload.get("commit"):
        issues.append(
            f"Skills SHA mismatch: lock={payload.get('commit')}, checkout={actual_sha}"
        )
    return {
        "ok": not issues,
        "issues": issues,
        "lock": payload,
        "actual_sha": actual_sha,
        "actual_contract_version": actual_contract,
        "git_error": git_error,
    }
