#!/usr/bin/env python3
"""Install one or more bundled skills into a Codex skills directory."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import sys

from install_ignore import ignore_patterns, remove_ignored_artifacts, should_ignore_relative


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skill"
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def default_destination(codex_home: Path | None = None) -> Path:
    if codex_home is None:
        env_home = os.environ.get("CODEX_HOME")
        codex_home = Path(env_home).expanduser() if env_home else Path.home() / ".codex"
    return codex_home / "skills"


def parse_skill_name(skill_dir: Path) -> str:
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"{skill_dir}/SKILL.md must start with YAML frontmatter")
    name_match = re.search(r"^name:\s*['\"]?([^'\"\n]+)['\"]?\s*$", match.group(1), re.M)
    if not name_match:
        raise ValueError(f"{skill_dir}/SKILL.md missing name")
    return name_match.group(1).strip()


def discover_skills() -> dict[str, Path]:
    skills: dict[str, Path] = {}
    for skill_dir in sorted(SKILL_ROOT.iterdir()):
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
            continue
        name = parse_skill_name(skill_dir)
        if name != skill_dir.name:
            raise ValueError(f"skill directory name must match frontmatter: {skill_dir.name!r} != {name!r}")
        skills[name] = skill_dir
    return skills


def selected_skills(all_skills: dict[str, Path], requested: list[str], include_all: bool) -> dict[str, Path]:
    if include_all or not requested:
        return all_skills

    selected = {}
    for name in requested:
        if name not in all_skills:
            choices = ", ".join(sorted(all_skills))
            raise ValueError(f"unknown skill {name!r}; available: {choices}")
        selected[name] = all_skills[name]
    return selected


def copy_skill(source: Path, destination: Path, dry_run: bool, prune: bool = False) -> None:
    if dry_run:
        print(f"DRY-RUN install {source.relative_to(REPO_ROOT)} -> {destination}")
        if prune:
            print(f"DRY-RUN prune stale files under {destination}")
        return

    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignore_patterns)
    remove_ignored_artifacts(destination)

    if prune:
        source_entries = {path.relative_to(source) for path in source.rglob("*") if not should_ignore_relative(path.relative_to(source))}
        for path in sorted(destination.rglob("*"), reverse=True):
            relative = path.relative_to(destination)
            if relative in source_entries and not should_ignore_relative(relative):
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def self_check_skill(skill_dir: Path) -> list[str]:
    issues: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    openai_yaml = skill_dir / "agents" / "openai.yaml"

    if not skill_md.exists():
        return [f"{skill_dir}: missing SKILL.md"]

    try:
        skill_name = parse_skill_name(skill_dir)
    except ValueError as exc:
        return [str(exc)]

    if skill_dir.name != skill_name:
        issues.append(f"{skill_dir}: directory name must be {skill_name}")

    if not openai_yaml.exists():
        issues.append(f"{skill_dir}: missing agents/openai.yaml")
    else:
        text = openai_yaml.read_text(encoding="utf-8")
        for required in ("display_name:", "short_description:", "default_prompt:"):
            if required not in text:
                issues.append(f"{openai_yaml}: missing {required}")
        if f"${skill_name}" not in text:
            issues.append(f"{openai_yaml}: default_prompt should mention ${skill_name}")

    return issues


def self_check_selected(destination_root: Path, skills: dict[str, Path]) -> int:
    issues: list[str] = []
    for name in skills:
        installed_dir = destination_root / name
        if not installed_dir.exists():
            issues.append(f"{installed_dir}: not installed")
            continue
        issues.extend(self_check_skill(installed_dir))

    if issues:
        print("install_self_check failed", file=sys.stderr)
        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        return 1

    print(f"install_self_check ok skills={len(skills)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Install bundled Codex skills.")
    parser.add_argument("--skill", action="append", default=[], help="Skill name to install. May be repeated.")
    parser.add_argument("--all", action="store_true", help="Install every skill under skill/. This is the default.")
    parser.add_argument(
        "--destination",
        type=Path,
        help="Destination skills directory. Defaults to CODEX_HOME/skills or the user home .codex/skills directory.",
    )
    parser.add_argument("--codex-home", type=Path, help="Codex home used to derive the destination.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files.")
    parser.add_argument("--self-check", action="store_true", help="Validate installed skill metadata after copying.")
    parser.add_argument("--self-check-only", action="store_true", help="Validate selected installed skills without copying.")
    args = parser.parse_args()

    if args.destination and args.codex_home:
        parser.error("--destination and --codex-home are mutually exclusive")

    destination_root = args.destination.expanduser() if args.destination else default_destination(args.codex_home)
    all_skills = discover_skills()
    skills = selected_skills(all_skills, args.skill, args.all)

    if args.self_check_only:
        return self_check_selected(destination_root, skills)

    for name, source in skills.items():
        copy_skill(source, destination_root / name, dry_run=args.dry_run)

    if args.self_check:
        if args.dry_run:
            issues = []
            for source in skills.values():
                issues.extend(self_check_skill(source))
            if issues:
                for issue in issues:
                    print(f"ERROR: {issue}", file=sys.stderr)
                return 1
            print(f"source_self_check ok skills={len(skills)}")
            return 0
        return self_check_selected(destination_root, skills)

    print(f"installed_skills {len(skills)} destination={destination_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
