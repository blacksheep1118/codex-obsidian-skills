#!/usr/bin/env python3
"""Check or sync shared script resources into independently installable skills."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import pprint
import stat
import sys

try:
    from .shared.safe_io import ensure_safe_output_path, safe_write_text
except ImportError:
    from shared.safe_io import ensure_safe_output_path, safe_write_text


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
        source=SHARED / "markdown_links.py",
        targets=(
            ROOT / "skill" / "ppt-to-md-for-obsidian" / "scripts" / "markdown_links.py",
            ROOT / "skill" / "obsidian-vault-organizer" / "scripts" / "markdown_links.py",
            ROOT / "skill" / "web-course-notes-for-obsidian" / "scripts" / "markdown_links.py",
            ROOT / "skill" / "notes-to-scientific-ppt" / "scripts" / "markdown_links.py",
        ),
    ),
    StaticResource(
        source=ROOT / "scripts" / "check_obsidian_links.py",
        targets=(
            ROOT / "skill" / "ppt-to-md-for-obsidian" / "scripts" / "check_obsidian_links.py",
            ROOT / "skill" / "obsidian-vault-organizer" / "scripts" / "check_obsidian_links.py",
            ROOT / "skill" / "web-course-notes-for-obsidian" / "scripts" / "check_obsidian_links.py",
            ROOT / "skill" / "notes-to-scientific-ppt" / "scripts" / "check_obsidian_links.py",
        ),
    ),
    StaticResource(
        source=SHARED / "safe_io.py",
        targets=(
            ROOT / "skill" / "ppt-to-md-for-obsidian" / "scripts" / "safe_io.py",
            ROOT / "skill" / "obsidian-vault-organizer" / "scripts" / "safe_io.py",
            ROOT / "skill" / "web-course-notes-for-obsidian" / "scripts" / "safe_io.py",
            ROOT / "skill" / "notes-to-scientific-ppt" / "scripts" / "safe_io.py",
            ROOT / "skill" / "solvenotes-vault-maintainer" / "scripts" / "safe_io.py",
        ),
    ),
    StaticResource(
        source=SHARED / "url_identity.py",
        targets=(
            ROOT / "skill" / "web-course-notes-for-obsidian" / "scripts" / "url_identity.py",
        ),
    ),
    StaticResource(
        source=ROOT
        / "skill"
        / "solvenotes-vault-maintainer"
        / "scripts"
        / "run_with_timeout.py",
        targets=(
            ROOT
            / "skill"
            / "algorithm-job-notes-for-obsidian"
            / "scripts"
            / "run_with_timeout.py",
            ROOT
            / "skill"
            / "ppt-to-md-for-obsidian"
            / "scripts"
            / "run_with_timeout.py",
        ),
    ),
    StaticResource(
        source=SHARED / "skill_metadata.py",
        targets=tuple(
            ROOT / "skill" / skill_name / "scripts" / "skill_metadata.py"
            for skill_name in (
                "ppt-to-md-for-obsidian",
                "obsidian-vault-organizer",
                "web-course-notes-for-obsidian",
                "notes-to-scientific-ppt",
                "solvenotes-vault-maintainer",
            )
        ),
    ),
)

VALIDATORS = (
    ValidatorResource(
        target=ROOT / "skill" / "notes-to-scientific-ppt" / "scripts" / "validate_skill.py",
        required_files=(
            "LICENSE",
            "requirements.txt",
            "agents/openai.yaml",
            "scripts/build_scientific_deck.py",
            "scripts/verify_pptx.py",
            "scripts/outline_note_deck.py",
            "scripts/check_obsidian_links.py",
            "scripts/markdown_links.py",
            "scripts/safe_io.py",
            "scripts/skill_metadata.py",
            "scripts/validate_skill.py",
            "references/scientific-deck-style.md",
            "references/deck-modes.md",
            "references/deck-qa.md",
        ),
    ),
    ValidatorResource(
        target=ROOT / "skill" / "web-course-notes-for-obsidian" / "scripts" / "validate_skill.py",
        required_files=(
            "LICENSE",
            "agents/openai.yaml",
            "scripts/collect_web_sources.py",
            "scripts/check_obsidian_links.py",
            "scripts/check_web_notes.py",
            "scripts/create_web_notes.py",
            "scripts/markdown_links.py",
            "scripts/safe_io.py",
            "scripts/url_identity.py",
            "scripts/skill_metadata.py",
            "scripts/validate_skill.py",
            "references/source-policy.md",
            "references/note-output.md",
        ),
    ),
    ValidatorResource(
        target=ROOT / "skill" / "obsidian-vault-organizer" / "scripts" / "validate_skill.py",
        required_files=(
            "LICENSE",
            "agents/openai.yaml",
            "scripts/check_obsidian_links.py",
            "scripts/check_vault_quality.py",
            "scripts/link_inventory.py",
            "scripts/markdown_links.py",
            "scripts/safe_io.py",
            "scripts/skill_metadata.py",
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
            "LICENSE",
            "agents/openai.yaml",
            "scripts/check_obsidian_links.py",
            "scripts/markdown_links.py",
            "scripts/check_course_notes.py",
            "scripts/check_source_coverage.py",
            "scripts/clean_latex_from_ppt.py",
            "scripts/convert_ppt_to_pptx.py",
            "scripts/extract_legacy_ppt_text.py",
            "scripts/extract_pdf_text.py",
            "scripts/extract_pptx_text.py",
            "scripts/ppt_to_obsidian_pipeline.py",
            "scripts/run_with_timeout.py",
            "scripts/safe_io.py",
            "scripts/skill_metadata.py",
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
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            output_mode = 0o644
        else:
            output_mode = stat.S_IMODE(mode) if stat.S_ISREG(mode) else 0o644
        safe_write_text(path, expected, mode=output_mode)
        return
    if not path.exists():
        mismatches.append(f"missing: {path.relative_to(ROOT)}")
        return
    if normalized_text(path) != expected:
        mismatches.append(f"out of sync: {path.relative_to(ROOT)}")


def resource_plan() -> list[tuple[Path, str]]:
    plan: list[tuple[Path, str]] = []
    for resource in STATIC_RESOURCES:
        expected = normalized_text(resource.source)
        plan.extend((target, expected) for target in resource.targets)
    plan.extend((resource.target, render_validator(resource)) for resource in VALIDATORS)
    return plan


def preflight_write_plan(plan: list[tuple[Path, str]]) -> None:
    """Validate every output before the first resource is changed."""

    for path, _expected in plan:
        ensure_safe_output_path(path, create_parent=False)


def apply_write_plan(plan: list[tuple[Path, str]]) -> None:
    preflight_write_plan(plan)
    for path, expected in plan:
        check_or_write(path, expected, True, [])


def sync(write: bool = False) -> list[str]:
    mismatches: list[str] = []
    plan = resource_plan()
    if write:
        apply_write_plan(plan)
        return mismatches
    for path, expected in plan:
        check_or_write(path, expected, False, mismatches)
    return mismatches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="rewrite skill-local copies from canonical shared resources")
    parser.add_argument("--check", action="store_true", help="check consistency without writing; default when --write is omitted")
    args = parser.parse_args()

    try:
        mismatches = sync(write=args.write)
    except (OSError, ValueError) as exc:
        print(f"ERROR: shared resource sync failed: {exc}", file=sys.stderr)
        return 1
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
