#!/usr/bin/env python3
"""Check or sync shared script resources into independently installable skills."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import pprint
import sys


ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "scripts" / "shared"


@dataclass(frozen=True)
class StaticResource:
    source: Path
    targets: tuple[Path, ...]


@dataclass(frozen=True)
class ValidatorResource:
    target: Path
    required_files: tuple[str, ...]
    success_message: str = "skill_validation ok"


STATIC_RESOURCES = (
    StaticResource(
        source=ROOT / "scripts" / "check_obsidian_links.py",
        targets=(
            ROOT / "skill" / "ppt-to-md-for-obsidian" / "scripts" / "check_obsidian_links.py",
            ROOT / "skill" / "obsidian-vault-organizer" / "scripts" / "check_obsidian_links.py",
        ),
    ),
)

VALIDATORS = (
    ValidatorResource(
        target=ROOT / "skill" / "notes-to-scientific-ppt" / "scripts" / "validate_skill.py",
        required_files=(
            "README.md",
            "LICENSE",
            "requirements.txt",
            "agents/openai.yaml",
            "scripts/build_scientific_deck.py",
            "scripts/outline_note_deck.py",
            "scripts/validate_skill.py",
            "references/scientific-deck-style.md",
            "references/deck-modes.md",
            "references/deck-qa.md",
        ),
    ),
    ValidatorResource(
        target=ROOT / "skill" / "web-course-notes-for-obsidian" / "scripts" / "validate_skill.py",
        required_files=(
            "README.md",
            "LICENSE",
            "agents/openai.yaml",
            "scripts/collect_web_sources.py",
            "scripts/check_web_notes.py",
            "scripts/create_web_notes.py",
            "scripts/validate_skill.py",
            "references/source-policy.md",
            "references/note-output.md",
        ),
    ),
    ValidatorResource(
        target=ROOT / "skill" / "obsidian-vault-organizer" / "scripts" / "validate_skill.py",
        required_files=(
            "README.md",
            "LICENSE",
            "agents/openai.yaml",
            "scripts/check_obsidian_links.py",
            "scripts/check_vault_quality.py",
            "scripts/link_inventory.py",
            "scripts/validate_skill.py",
            "references/project-vault-workflow.md",
            "references/obsidian-style.md",
            "references/validation.md",
            "references/solvenotes-profile.md",
        ),
    ),
    ValidatorResource(
        target=ROOT / "skill" / "ppt-to-md-for-obsidian" / "scripts" / "validate_skill_repo.py",
        required_files=(
            "README.md",
            "LICENSE",
            "agents/openai.yaml",
            "scripts/check_obsidian_links.py",
            "scripts/check_course_notes.py",
            "scripts/check_source_coverage.py",
            "scripts/clean_latex_from_ppt.py",
            "scripts/convert_ppt_to_pptx.py",
            "scripts/extract_legacy_ppt_text.py",
            "scripts/extract_pdf_text.py",
            "scripts/extract_pptx_text.py",
            "scripts/ppt_to_obsidian_pipeline.py",
            "scripts/validate_skill_repo.py",
            "references/modes.md",
            "references/obsidian-style.md",
            "references/validation.md",
            "references/solvenotes-profile.md",
        ),
        success_message="skill_repo_validation ok",
    ),
)


def normalized_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def render_validator(resource: ValidatorResource) -> str:
    template = normalized_text(SHARED / "validate_skill.py.in")
    required = pprint.pformat(list(resource.required_files), width=100)
    rendered = template.replace("__REQUIRED_FILES__", required)
    rendered = rendered.replace("__SUCCESS_MESSAGE__", resource.success_message)
    return rendered


def check_or_write(path: Path, expected: str, write: bool, mismatches: list[str]) -> None:
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected, encoding="utf-8")
        return
    if not path.exists():
        mismatches.append(f"missing: {path.relative_to(ROOT)}")
        return
    if normalized_text(path) != expected:
        mismatches.append(f"out of sync: {path.relative_to(ROOT)}")


def sync(write: bool = False) -> list[str]:
    mismatches: list[str] = []
    for resource in STATIC_RESOURCES:
        expected = normalized_text(resource.source)
        for target in resource.targets:
            check_or_write(target, expected, write, mismatches)
    for resource in VALIDATORS:
        check_or_write(resource.target, render_validator(resource), write, mismatches)
    return mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="rewrite skill-local copies from canonical shared resources")
    parser.add_argument("--check", action="store_true", help="check consistency without writing; default when --write is omitted")
    args = parser.parse_args()

    mismatches = sync(write=args.write)
    if args.write:
        print("shared_resource_sync wrote resources")
        return 0
    if mismatches:
        print("shared_resource_sync failed", file=sys.stderr)
        for mismatch in mismatches:
            print(f"ERROR: {mismatch}", file=sys.stderr)
        print("Run: python scripts/sync_shared_resources.py --write", file=sys.stderr)
        return 1
    print("shared_resource_sync ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
