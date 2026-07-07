#!/usr/bin/env python3
"""Run the full repository validation suite used by CI."""

from __future__ import annotations

import os
import argparse
from dataclasses import dataclass
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PPT_SKILL = ROOT / "skill" / "ppt-to-md-for-obsidian"
VAULT_SKILL = ROOT / "skill" / "obsidian-vault-organizer"
WEB_SKILL = ROOT / "skill" / "web-course-notes-for-obsidian"
NOTES_PPT_SKILL = ROOT / "skill" / "notes-to-scientific-ppt"
TMP = Path(tempfile.gettempdir())
INSTALL_TMP = TMP / "codex-obsidian-skills-validate-install"
PIPELINE_TMP = TMP / "codex-obsidian-skills-pipeline-out"
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("VALIDATE_ALL_TIMEOUT_SECONDS", "180"))
SKILL_ALIASES = {
    "ppt-to-md-for-obsidian": "ppt",
    "web-course-notes-for-obsidian": "web",
    "obsidian-vault-organizer": "vault",
    "notes-to-scientific-ppt": "notes",
}


@dataclass(frozen=True)
class CommandSpec:
    command: list[str]
    cwd: Path = ROOT


@dataclass(frozen=True)
class Step:
    step_id: str
    commands: tuple[CommandSpec, ...]
    skill: str | None = None
    quick: bool = True


def format_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def format_cwd(cwd: Path) -> str:
    try:
        return str(cwd.relative_to(ROOT)) if cwd != ROOT else "."
    except ValueError:
        return str(cwd)


def report_failure(step_id: str, command: list[str], cwd: Path, returncode: int | str, timeout: int | None = None) -> None:
    print("\nvalidation command failed", file=sys.stderr, flush=True)
    print(f"step: {step_id}", file=sys.stderr, flush=True)
    print(f"cwd: {cwd}", file=sys.stderr, flush=True)
    print(f"command: {format_command(command)}", file=sys.stderr, flush=True)
    print(f"return code: {returncode}", file=sys.stderr, flush=True)
    if timeout is not None:
        print(f"timeout: after {timeout}s", file=sys.stderr, flush=True)


def run_command(step_id: str, command: list[str], cwd: Path, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> None:
    print(f"\nstep: {step_id}", flush=True)
    print(f"cwd: {format_cwd(cwd)}", flush=True)
    print(f"command: {format_command(command)}", flush=True)
    try:
        subprocess.run(command, cwd=cwd, check=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        report_failure(step_id, command, cwd, "timeout", timeout=timeout)
        raise SystemExit(124) from None
    except subprocess.CalledProcessError as exc:
        report_failure(step_id, command, cwd, exc.returncode)
        raise SystemExit(exc.returncode) from None
    print(f"{step_id} ok", flush=True)


def build_steps(py: str) -> list[Step]:
    return [
        Step("root.compile", (CommandSpec([py, "-m", "compileall", "scripts"]),)),
        Step("root.repo_hygiene", (CommandSpec([py, "scripts/check_repo_hygiene.py"]),)),
        Step(
            "metadata.sync",
            (
                CommandSpec([py, "scripts/check_openai_yaml_sync.py"]),
                CommandSpec([py, "scripts/sync_shared_resources.py", "--check"]),
                CommandSpec([py, "scripts/install_skill.py", "--all", "--dry-run", "--self-check"]),
            ),
        ),
        Step(
            "metadata.install",
            (
                CommandSpec([py, "scripts/install_skill.py", "--all", "--destination", str(INSTALL_TMP), "--self-check"]),
                CommandSpec([py, "scripts/update_installed_skills.py", "--all", "--destination", str(INSTALL_TMP), "--dry-run", "--prune"]),
            ),
            quick=False,
        ),
        Step("root.tests", (CommandSpec([py, "-m", "pytest", "-q"]),)),
        Step("ppt.compile", (CommandSpec([py, "-m", "compileall", "scripts"], cwd=PPT_SKILL),), skill="ppt"),
        Step("ppt.tests", (CommandSpec([py, "-m", "pytest", "-q", "tests"], cwd=PPT_SKILL),), skill="ppt", quick=False),
        Step("ppt.validator", (CommandSpec([py, "scripts/validate_skill_repo.py"], cwd=PPT_SKILL),), skill="ppt"),
        Step(
            "ppt.pipeline",
            (
                CommandSpec([py, "scripts/extract_pptx_text.py", "examples/sample-course/raw/sample_course.pptx", "--out", str(TMP / "sample_course_extracted.md")], cwd=PPT_SKILL),
                CommandSpec([py, "scripts/clean_latex_from_ppt.py", "examples/sample-course/extracted/sample_course_extracted.md", "--unicode-math", "--out", str(TMP / "sample_course_cleaned.md")], cwd=PPT_SKILL),
                CommandSpec([py, "scripts/ppt_to_obsidian_pipeline.py", "--config", "skill-config.example.yaml", "--output-dir", str(PIPELINE_TMP)], cwd=PPT_SKILL),
                CommandSpec([py, "scripts/check_obsidian_links.py", "examples/sample-course/notes"], cwd=PPT_SKILL),
                CommandSpec([py, "scripts/check_course_notes.py", "examples/sample-course/notes"], cwd=PPT_SKILL),
            ),
            skill="ppt",
            quick=False,
        ),
        Step("vault.compile", (CommandSpec([py, "-m", "compileall", "scripts"], cwd=VAULT_SKILL),), skill="vault"),
        Step("vault.tests", (CommandSpec([py, "-m", "pytest", "-q", "tests"], cwd=VAULT_SKILL),), skill="vault", quick=False),
        Step("vault.validator", (CommandSpec([py, "scripts/validate_skill.py"], cwd=VAULT_SKILL),), skill="vault"),
        Step(
            "vault.pipeline",
            (
                CommandSpec([py, "scripts/check_obsidian_links.py", "../ppt-to-md-for-obsidian/examples/sample-course/notes"], cwd=VAULT_SKILL),
                CommandSpec([py, "scripts/check_vault_quality.py", "../../fixtures/vault-clean"], cwd=VAULT_SKILL),
            ),
            skill="vault",
            quick=False,
        ),
        Step("web.compile", (CommandSpec([py, "-m", "compileall", "scripts"], cwd=WEB_SKILL),), skill="web"),
        Step("web.tests", (CommandSpec([py, "-m", "pytest", "-q", "tests"], cwd=WEB_SKILL),), skill="web", quick=False),
        Step("web.validator", (CommandSpec([py, "scripts/validate_skill.py"], cwd=WEB_SKILL),), skill="web"),
        Step(
            "web.pipeline",
            (
                CommandSpec([py, "scripts/collect_web_sources.py", "examples/sample-web-course/index.html", "--out", str(TMP / "web_course_source_manifest.md")], cwd=WEB_SKILL),
                CommandSpec([py, "scripts/create_web_notes.py", "https://example.com/papers/Zhu_From_Noise_Modeling_CVPR_2016_paper.pdf", "--notes-dir", str(TMP / "codex-obsidian-skills-web-notes"), "--dry-run"], cwd=WEB_SKILL),
            ),
            skill="web",
            quick=False,
        ),
        Step("notes.compile", (CommandSpec([py, "-m", "compileall", "scripts"], cwd=NOTES_PPT_SKILL),), skill="notes"),
        Step("notes.tests", (CommandSpec([py, "-m", "pytest", "-q", "tests"], cwd=NOTES_PPT_SKILL),), skill="notes", quick=False),
        Step("notes.validator", (CommandSpec([py, "scripts/validate_skill.py"], cwd=NOTES_PPT_SKILL),), skill="notes"),
        Step(
            "notes.deck",
            (
                CommandSpec(
                    [
                        py,
                        "scripts/outline_note_deck.py",
                        "examples/sample-notes",
                        "--out",
                        str(TMP / "scientific_deck_brief.md"),
                        "--title",
                        "Blind Image Denoising",
                        "--mode",
                        "paper-reading",
                    ],
                    cwd=NOTES_PPT_SKILL,
                ),
            ),
            skill="notes",
            quick=False,
        ),
    ]


def selected_steps(steps: list[Step], quick: bool, skill: str | None) -> list[Step]:
    if skill is not None:
        skill_key = SKILL_ALIASES[skill]
        return [step for step in steps if step.skill == skill_key and (step.quick or not quick)]
    return [step for step in steps if step.quick or not quick]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="run compile, root tests, repo hygiene, metadata sync, and skill validators; skip skill tests and sample pipeline/deck smoke runs",
    )
    parser.add_argument("--skill", choices=sorted(SKILL_ALIASES), help="run validation stages only for one skill")
    parser.add_argument("--list-steps", action="store_true", help="list stable validation step ids and exit")
    args = parser.parse_args(argv)
    py = sys.executable
    steps = build_steps(py)

    if args.list_steps:
        for step in steps:
            print(step.step_id)
        return 0

    for step in selected_steps(steps, quick=args.quick, skill=args.skill):
        for command in step.commands:
            run_command(step.step_id, command.command, command.cwd)

    suffix = " quick" if args.quick else ""
    skill_text = f" skill={args.skill}" if args.skill else ""
    print(f"\nvalidate_all{suffix}{skill_text} ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
