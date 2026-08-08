#!/usr/bin/env python3
"""Validate skill frontmatter and agents/openai.yaml metadata consistency."""

from __future__ import annotations

from pathlib import Path
import sys

from shared.skill_metadata import (
    MetadataValidationError,
    load_skill_frontmatter as load_skill_frontmatter_file,
    validate_openai_yaml as validate_openai_yaml_file,
)


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skill"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_skill_frontmatter(skill_dir: Path) -> dict:
    path = skill_dir / "SKILL.md"
    if not path.exists():
        fail(f"{skill_dir.relative_to(ROOT)} is missing SKILL.md")
    try:
        return load_skill_frontmatter_file(path, expected_name=skill_dir.name)
    except (OSError, MetadataValidationError) as exc:
        fail(str(exc))


def validate_openai_yaml(skill_dir: Path, skill_name: str) -> None:
    path = skill_dir / "agents" / "openai.yaml"
    if not path.exists():
        fail(f"{path.relative_to(ROOT)} is missing")
    try:
        validate_openai_yaml_file(path, skill_name)
    except (OSError, MetadataValidationError) as exc:
        fail(str(exc))


def main() -> int:
    skill_dirs = sorted(path for path in SKILL_ROOT.iterdir() if path.is_dir() and (path / "SKILL.md").exists())
    if not skill_dirs:
        fail("no installable skills found under skill/")

    for skill_dir in skill_dirs:
        metadata = load_skill_frontmatter(skill_dir)
        validate_openai_yaml(skill_dir, metadata["name"])

    print(f"openai_yaml_sync ok skills={len(skill_dirs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
