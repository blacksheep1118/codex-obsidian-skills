#!/usr/bin/env python3
"""Validate skill frontmatter and agents/openai.yaml metadata consistency."""

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skill"
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_yaml(text: str):
    try:
        import yaml
    except ImportError as exc:
        fail(f"PyYAML is required for YAML validation: {exc}")
    return yaml.safe_load(text)


def load_skill_frontmatter(skill_dir: Path) -> dict:
    path = skill_dir / "SKILL.md"
    if not path.exists():
        fail(f"{skill_dir.relative_to(ROOT)} is missing SKILL.md")
    match = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        fail(f"{path.relative_to(ROOT)} must start with YAML frontmatter")
    metadata = load_yaml(match.group(1))
    for key in ("name", "description"):
        if not metadata.get(key):
            fail(f"{path.relative_to(ROOT)} missing frontmatter {key}")
    if metadata["name"] != skill_dir.name:
        fail(f"{path.relative_to(ROOT)} name {metadata['name']!r} does not match directory {skill_dir.name!r}")
    return metadata


def validate_openai_yaml(skill_dir: Path, skill_name: str) -> None:
    path = skill_dir / "agents" / "openai.yaml"
    if not path.exists():
        fail(f"{path.relative_to(ROOT)} is missing")
    data = load_yaml(path.read_text(encoding="utf-8"))
    interface = data.get("interface", {})
    for key in ("display_name", "short_description", "default_prompt"):
        if not interface.get(key):
            fail(f"{path.relative_to(ROOT)} missing interface.{key}")
    default_prompt = interface["default_prompt"]
    if f"${skill_name}" not in default_prompt:
        fail(f"{path.relative_to(ROOT)} default_prompt must mention ${skill_name}")


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
