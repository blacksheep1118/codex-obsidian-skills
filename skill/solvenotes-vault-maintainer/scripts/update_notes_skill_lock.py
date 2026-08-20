#!/usr/bin/env python3
"""Update the Notes-to-Skills lock after validating a local Skills ref.

The command is deliberately dry-run by default. It never commits or pushes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from vault_contract import (
    CURRENT_VAULT_CONTRACT_VERSION,
    FULL_SHA_RE,
    MAINTAINER_SKILL,
    SKILLS_REPOSITORY,
    lock_path,
    maintainer_root,
)

REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


def resolve_commit(skills_root: Path, ref: str) -> str:
    if not ref or not REF_RE.fullmatch(ref) or ref.startswith("-"):
        raise ValueError("skills-ref must be a non-empty Git ref without shell punctuation")
    try:
        result = subprocess.run(
            ["git", "-C", str(skills_root), "rev-parse", "--verify", f"{ref}^{{commit}}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"cannot resolve Skills ref: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or f"git exited {result.returncode}"
        raise ValueError(f"Skills ref does not resolve to a commit: {detail}")
    commit = result.stdout.strip()
    if not FULL_SHA_RE.fullmatch(commit):
        raise ValueError(f"resolved Skills ref is not a full SHA: {commit!r}")
    return commit


def current_lock(notes_root: Path) -> dict[str, object] | None:
    path = lock_path(notes_root)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"existing lock is not a JSON object: {path}")
    return value


def target_contract_version(skills_root: Path) -> int:
    path = maintainer_root(skills_root) / "scripts" / "vault_contract.py"
    text = path.read_text(encoding="utf-8")
    marker = "CURRENT_VAULT_CONTRACT_VERSION = "
    for line in text.splitlines():
        if line.startswith(marker):
            value = int(line[len(marker) :].strip())
            return value
    raise ValueError(f"missing {marker.strip()} in {path}")


def write_lock(notes_root: Path, payload: dict[str, object]) -> None:
    destination = lock_path(notes_root)
    if destination.parent.exists() and destination.parent.is_symlink():
        raise ValueError(f"lock directory must not be a symlink: {destination.parent}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.parent.is_dir():
        raise ValueError(f"lock directory must be a regular directory: {destination.parent}")
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notes-root", type=Path, required=True)
    parser.add_argument("--skills-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--skills-ref", required=True)
    parser.add_argument("--write", action="store_true", help="write the validated lock; default is dry-run")
    args = parser.parse_args(argv)
    notes_root = args.notes_root.resolve()
    skills_root = args.skills_root.resolve()
    try:
        commit = resolve_commit(skills_root, args.skills_ref)
        if not (maintainer_root(skills_root) / "SKILL.md").is_file():
            raise ValueError(f"missing Skill {MAINTAINER_SKILL!r} in {skills_root}")
        contract_version = target_contract_version(skills_root)
        if contract_version != CURRENT_VAULT_CONTRACT_VERSION:
            raise ValueError(
                f"source contract mismatch: expected {CURRENT_VAULT_CONTRACT_VERSION}, got {contract_version}"
            )
        old = current_lock(notes_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    payload = {
        "repository": SKILLS_REPOSITORY,
        "commit": commit,
        "maintainer_skill": MAINTAINER_SKILL,
        "contract_version": contract_version,
    }
    print(f"lock_path {lock_path(notes_root)}")
    print("current_lock " + (json.dumps(old, ensure_ascii=False, sort_keys=True) if old else "MISSING"))
    print("proposed_lock " + json.dumps(payload, ensure_ascii=False, sort_keys=True))
    if not args.write:
        print("mode dry-run")
        return 0
    write_lock(notes_root, payload)
    print("mode write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
