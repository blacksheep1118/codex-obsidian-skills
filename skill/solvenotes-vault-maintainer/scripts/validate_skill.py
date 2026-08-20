#!/usr/bin/env python3
"""Validate this project Skill's metadata and external-vault entry points."""

from __future__ import annotations

import sys
from pathlib import Path

from skill_metadata import (
    MetadataValidationError,
    load_skill_frontmatter,
    validate_openai_yaml,
)

SKILL_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        metadata = load_skill_frontmatter(SKILL_ROOT / "SKILL.md", expected_name=SKILL_ROOT.name)
        validate_openai_yaml(SKILL_ROOT / "agents" / "openai.yaml", metadata["name"])
    except (OSError, MetadataValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    required = (
        SKILL_ROOT / "scripts" / "dev_check.sh",
        SKILL_ROOT / "scripts" / "check_all_notes.py",
        SKILL_ROOT / "scripts" / "doctor.py",
        SKILL_ROOT / "scripts" / "check_skills_lock.py",
        SKILL_ROOT / "scripts" / "check_workspace_guidance.py",
        SKILL_ROOT / "scripts" / "check_documented_commands.py",
        SKILL_ROOT / "scripts" / "update_notes_skill_lock.py",
        SKILL_ROOT / "scripts" / "vault_contract.py",
        SKILL_ROOT / "scripts" / "package_vault.py",
        SKILL_ROOT / "scripts" / "package_workspace.py",
        SKILL_ROOT / "scripts" / "verify_workspace_package.py",
        SKILL_ROOT / "scripts" / "safe_io.py",
        SKILL_ROOT / "scripts" / "skill_metadata.py",
        SKILL_ROOT / "scripts" / "run_with_timeout.py",
        SKILL_ROOT / "tests",
    )
    missing = [str(path.relative_to(SKILL_ROOT)) for path in required if not path.exists()]
    if missing:
        print(f"ERROR: missing project Skill entry points: {', '.join(missing)}", file=sys.stderr)
        return 1
    print(f"solvenotes_vault_maintainer_validator ok name={metadata['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
