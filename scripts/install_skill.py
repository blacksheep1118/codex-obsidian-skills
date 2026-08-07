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


class UnsafeDestinationError(ValueError):
    """Raised when an install target could escape through a symlink."""


def ensure_safe_destination_root(destination_root: Path) -> None:
    """Reject a destination root that is itself a symlink or non-directory."""

    if destination_root.is_symlink():
        raise UnsafeDestinationError(f"unsafe destination symlink: {destination_root}")
    if destination_root.exists() and not destination_root.is_dir():
        raise UnsafeDestinationError(f"destination root is not a directory: {destination_root}")


def ensure_safe_destination_tree(destination: Path) -> None:
    """Reject existing or dangling symlinks anywhere in a destination skill tree."""

    ensure_safe_destination_root(destination.parent)
    if destination.is_symlink():
        raise UnsafeDestinationError(f"unsafe destination symlink: {destination}")
    if not destination.exists():
        return
    if not destination.is_dir():
        raise UnsafeDestinationError(f"destination skill is not a directory: {destination}")

    for current_root, directory_names, file_names in os.walk(destination, followlinks=False):
        current = Path(current_root)
        for name in (*directory_names, *file_names):
            candidate = current / name
            if candidate.is_symlink():
                raise UnsafeDestinationError(f"unsafe destination symlink: {candidate}")


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


def managed_files(root: Path) -> dict[Path, Path]:
    """Return installable files without following ignored/generated artifacts."""

    if not root.exists():
        return {}
    return {
        path.relative_to(root): path
        for path in root.rglob("*")
        if path.is_file() and not should_ignore_relative(path.relative_to(root))
    }


def compare_skill(source: Path, destination: Path) -> dict[str, list[str]]:
    """Compare managed files without mutating either tree."""

    source_files = managed_files(source)
    destination_files = managed_files(destination)
    added = sorted(relative.as_posix() for relative in source_files.keys() - destination_files.keys())
    stale = sorted(relative.as_posix() for relative in destination_files.keys() - source_files.keys())
    changed = sorted(
        relative.as_posix()
        for relative in source_files.keys() & destination_files.keys()
        if source_files[relative].read_bytes() != destination_files[relative].read_bytes()
    )
    unchanged = sorted(
        relative.as_posix()
        for relative in source_files.keys() & destination_files.keys()
        if source_files[relative].read_bytes() == destination_files[relative].read_bytes()
    )
    return {"added": added, "changed": changed, "unchanged": unchanged, "stale": stale}


def copy_skill(source: Path, destination: Path, dry_run: bool, prune: bool = False) -> None:
    ensure_safe_destination_tree(destination)
    if dry_run:
        diff = compare_skill(source, destination)
        print(
            f"DRY-RUN install {source.relative_to(REPO_ROOT)} -> {destination} "
            f"added={len(diff['added'])} changed={len(diff['changed'])} "
            f"unchanged={len(diff['unchanged'])} stale={len(diff['stale'])}"
        )
        for kind in ("added", "changed", "stale"):
            for relative in diff[kind]:
                print(f"DRY-RUN {kind} {relative}")
        if prune:
            print(f"DRY-RUN prune stale files under {destination}: {len(diff['stale'])}")
        else:
            print(f"DRY-RUN prune not requested for {destination}")
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


def report_self_check(label: str, issues: list[str], skill_count: int) -> int:
    if issues:
        print(f"{label} failed", file=sys.stderr)
        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        return 1

    print(f"{label} ok skills={skill_count}")
    return 0


def self_check_sources(skills: dict[str, Path]) -> int:
    issues: list[str] = []
    for source in skills.values():
        issues.extend(self_check_skill(source))
    return report_self_check("source_self_check", issues, len(skills))


def self_check_selected(destination_root: Path, skills: dict[str, Path]) -> int:
    issues: list[str] = []
    try:
        ensure_safe_destination_root(destination_root)
    except UnsafeDestinationError as exc:
        issues.append(str(exc))
        return report_self_check("install_self_check", issues, len(skills))

    for name in skills:
        installed_dir = destination_root / name
        try:
            ensure_safe_destination_tree(installed_dir)
        except UnsafeDestinationError as exc:
            issues.append(str(exc))
            continue
        if not installed_dir.exists():
            issues.append(f"{installed_dir}: not installed")
            continue
        issues.extend(self_check_skill(installed_dir))

    return report_self_check("install_self_check", issues, len(skills))


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

    try:
        ensure_safe_destination_root(destination_root)
        for name, source in skills.items():
            copy_skill(source, destination_root / name, dry_run=args.dry_run)
    except UnsafeDestinationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.self_check:
        if args.dry_run:
            return self_check_sources(skills)
        return self_check_selected(destination_root, skills)

    print(f"installed_skills {len(skills)} destination={destination_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
