#!/usr/bin/env python3
"""Validate the skill repository structure and lightweight metadata."""

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


def validate_skill() -> None:
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


def validate_openai_yaml() -> None:
    path = ROOT / "agents" / "openai.yaml"
    if not path.exists():
        fail("agents/openai.yaml is missing")
    data = load_yaml(path.read_text(encoding="utf-8"))
    interface = data.get("interface", {})
    for key in ("display_name", "short_description", "default_prompt"):
        if not interface.get(key):
            fail(f"agents/openai.yaml missing interface.{key}")
    skill_name = load_yaml(FRONTMATTER_RE.match((ROOT / "SKILL.md").read_text(encoding="utf-8")).group(1))["name"]
    if f"${skill_name}" not in interface["default_prompt"]:
        fail("interface.default_prompt must mention the skill name with $skill-name")


def validate_all_yaml_files() -> None:
    for path in sorted(ROOT.rglob("*.yml")) + sorted(ROOT.rglob("*.yaml")):
        if ".git" in path.parts:
            continue
        try:
            load_yaml(path.read_text(encoding="utf-8"))
        except Exception as exc:
            fail(f"invalid YAML in {path.relative_to(ROOT)}: {exc}")


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
        if target and not (ROOT / target).exists():
            fail(f"README.md link target does not exist: {target}")


def validate_required_files() -> None:
    required = [
        "README.md",
        "LICENSE",
        "agents/openai.yaml",
        "scripts/check_obsidian_links.py",
        "scripts/check_course_notes.py",
        "scripts/clean_latex_from_ppt.py",
        "scripts/convert_ppt_to_pptx.py",
        "scripts/extract_pdf_text.py",
        "scripts/extract_pptx_text.py",
        "scripts/ppt_to_obsidian_pipeline.py",
        "scripts/validate_skill_repo.py",
        "references/modes.md",
        "references/obsidian-style.md",
        "references/validation.md",
    ]
    for target in required:
        if not (ROOT / target).exists():
            fail(f"required bundled file is missing: {target}")


def validate_references_exist() -> None:
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for target in re.findall(r"`(references/[^`]+\.md|scripts/[^`]+\.py)`", text):
        if not (ROOT / target).exists():
            fail(f"referenced bundled resource is missing: {target}")


def main() -> int:
    validate_skill()
    validate_openai_yaml()
    validate_required_files()
    validate_all_yaml_files()
    validate_references_exist()
    validate_readme_links()
    print("skill_repo_validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
