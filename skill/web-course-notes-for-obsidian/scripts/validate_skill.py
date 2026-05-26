#!/usr/bin/env python3
"""Validate the skill folder structure and lightweight metadata."""

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
MD_LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)]+)\)")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_yaml(text: str):
    try:
        import yaml
    except ImportError as exc:
        fail(f"PyYAML is required for YAML validation: {exc}")
    return yaml.safe_load(text)


def load_skill_metadata() -> dict:
    path = ROOT / "SKILL.md"
    if not path.exists():
        fail("SKILL.md is missing")
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        fail("SKILL.md must start with YAML frontmatter")
    data = load_yaml(match.group(1))
    for key in ("name", "description"):
        if not data.get(key):
            fail(f"SKILL.md frontmatter missing {key}")
    if ROOT.name != data["name"]:
        fail(f"skill directory name must match SKILL.md frontmatter name: {ROOT.name!r} != {data['name']!r}")
    return data


def validate_openai_yaml(skill_name: str) -> None:
    path = ROOT / "agents" / "openai.yaml"
    if not path.exists():
        fail("agents/openai.yaml is missing")
    data = load_yaml(path.read_text(encoding="utf-8"))
    interface = data.get("interface", {})
    for key in ("display_name", "short_description", "default_prompt"):
        if not interface.get(key):
            fail(f"agents/openai.yaml missing interface.{key}")
    if f"${skill_name}" not in interface["default_prompt"]:
        fail("interface.default_prompt must mention the skill name with $skill-name")


def validate_yaml_files() -> None:
    for path in sorted(ROOT.rglob("*.yml")) + sorted(ROOT.rglob("*.yaml")):
        if ".git" in path.parts:
            continue
        try:
            load_yaml(path.read_text(encoding="utf-8"))
        except Exception as exc:
            fail(f"invalid YAML in {path.relative_to(ROOT)}: {exc}")


def validate_references_exist() -> None:
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for target in re.findall(r"`(references/[^`]+\.md|scripts/[^`]+\.py)`", text):
        if not (ROOT / target).exists():
            fail(f"referenced bundled resource is missing: {target}")


def validate_required_files() -> None:
    required = [
        "README.md",
        "LICENSE",
        "agents/openai.yaml",
        "scripts/collect_web_sources.py",
        "scripts/validate_skill.py",
        "references/source-policy.md",
        "references/note-output.md",
    ]
    for target in required:
        if not (ROOT / target).exists():
            fail(f"required bundled file is missing: {target}")


def validate_readme_links() -> None:
    path = ROOT / "README.md"
    if not path.exists():
        fail("README.md is missing")
    text = path.read_text(encoding="utf-8")
    for target in MD_LINK_RE.findall(text):
        target = target.strip()
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = target.split("#", 1)[0]
        if target and not (ROOT / target).resolve().exists():
            fail(f"README.md link target does not exist: {target}")


def main() -> int:
    metadata = load_skill_metadata()
    validate_openai_yaml(metadata["name"])
    validate_required_files()
    validate_yaml_files()
    validate_references_exist()
    validate_readme_links()
    print("skill_validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
