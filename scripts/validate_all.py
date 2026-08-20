#!/usr/bin/env python3
"""Run the full repository validation suite used by CI."""

from __future__ import annotations

import os
import argparse
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import shlex
import sys
import tempfile
from collections.abc import Mapping


ROOT = Path(__file__).resolve().parents[1]
_TIMEOUT_HELPER = ROOT / "skill" / "solvenotes-vault-maintainer" / "scripts" / "run_with_timeout.py"
_TIMEOUT_SPEC = importlib.util.spec_from_file_location("_solvenotes_timeout_runner_validate", _TIMEOUT_HELPER)
if _TIMEOUT_SPEC is None or _TIMEOUT_SPEC.loader is None:
    raise ImportError(f"cannot load timeout helper: {_TIMEOUT_HELPER}")
_TIMEOUT_MODULE = importlib.util.module_from_spec(_TIMEOUT_SPEC)
_TIMEOUT_SPEC.loader.exec_module(_TIMEOUT_MODULE)
run_process = _TIMEOUT_MODULE.run


RUFF_CONFIG = ROOT / "pyproject.toml"
PPT_SKILL = ROOT / "skill" / "ppt-to-md-for-obsidian"
VAULT_SKILL = ROOT / "skill" / "obsidian-vault-organizer"
WEB_SKILL = ROOT / "skill" / "web-course-notes-for-obsidian"
NOTES_PPT_SKILL = ROOT / "skill" / "notes-to-scientific-ppt"
ALGORITHM_JOB_SKILL = ROOT / "skill" / "algorithm-job-notes-for-obsidian"
SOLVENOTES_VAULT_SKILL = ROOT / "skill" / "solvenotes-vault-maintainer"
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("VALIDATE_ALL_TIMEOUT_SECONDS", "180"))
PYTHON_BIN_OVERRIDE = "SOLVENOTES_PYTHON_BIN"
PYTEST_PLUGIN_AUTOLOAD_OVERRIDE = "VALIDATE_ALL_ENABLE_PYTEST_PLUGIN_AUTOLOAD"
TRUE_VALUES = {"1", "true", "yes", "on"}
SKILL_ALIASES = {
    "ppt-to-md-for-obsidian": "ppt",
    "web-course-notes-for-obsidian": "web",
    "obsidian-vault-organizer": "vault",
    "notes-to-scientific-ppt": "notes",
    "algorithm-job-notes-for-obsidian": "algorithm-job",
    "solvenotes-vault-maintainer": "solvenotes-vault",
}
SKILL_ALIAS_TO_FULL = {alias: full_name for full_name, alias in SKILL_ALIASES.items()}


@dataclass(frozen=True)
class CommandSpec:
    command: list[str]
    cwd: Path = ROOT
    env: Mapping[str, str] | None = None


@dataclass(frozen=True)
class Step:
    step_id: str
    commands: tuple[CommandSpec, ...]
    skill: str | None = None
    quick: bool = True


def format_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def format_skill_choices() -> str:
    return ", ".join(f"{full_name} ({alias})" for full_name, alias in sorted(SKILL_ALIASES.items()))


def normalize_skill(skill: str | None) -> str | None:
    if skill is None:
        return None
    if skill in SKILL_ALIASES:
        return SKILL_ALIASES[skill]
    if skill in SKILL_ALIAS_TO_FULL:
        return skill
    raise ValueError(f"unknown skill: {skill}. Valid skills: {format_skill_choices()}")


def format_cwd(cwd: Path) -> str:
    try:
        return str(cwd.relative_to(ROOT)) if cwd != ROOT else "."
    except ValueError:
        return str(cwd)


def report_failure(
    step_id: str,
    command: list[str],
    cwd: Path,
    returncode: int | str,
    timeout: int | None = None,
    stdout: str | bytes | None = None,
    stderr: str | bytes | None = None,
) -> None:
    print("\nvalidation command failed", file=sys.stderr, flush=True)
    print(f"step: {step_id}", file=sys.stderr, flush=True)
    print(f"cwd: {cwd}", file=sys.stderr, flush=True)
    print(f"command: {format_command(command)}", file=sys.stderr, flush=True)
    print(f"return code: {returncode}", file=sys.stderr, flush=True)
    if timeout is not None:
        print(f"timeout: after {timeout}s", file=sys.stderr, flush=True)
    for label, output in (("stdout", stdout), ("stderr", stderr)):
        if output:
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            print(f"{label}:\n{output.rstrip()}", file=sys.stderr, flush=True)


def subprocess_env(extra: Mapping[str, str] | None) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra:
        env.update(extra)
    return env


def pytest_env() -> dict[str, str]:
    env = {"PYTHONDONTWRITEBYTECODE": "1"}
    override = os.environ.get(PYTEST_PLUGIN_AUTOLOAD_OVERRIDE, "").strip().lower()
    if override in TRUE_VALUES:
        return env
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return env


def pytest_command(
    py: str,
    *args: str,
    cwd: Path = ROOT,
    extra_env: Mapping[str, str] | None = None,
) -> CommandSpec:
    env = pytest_env()
    if extra_env:
        env.update(extra_env)
    return CommandSpec(
        [py, "-m", "pytest", *args, "--durations=20", "-p", "no:cacheprovider"],
        cwd=cwd,
        env=env,
    )


def compile_command(py: str, temp_root: Path, cwd: Path = ROOT) -> CommandSpec:
    return CommandSpec(
        [py, "-m", "compileall", "scripts"],
        cwd=cwd,
        env={"PYTHONPYCACHEPREFIX": str(temp_root / "pycache")},
    )


def run_command(
    step_id: str,
    command: list[str],
    cwd: Path,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    env: Mapping[str, str] | None = None,
) -> None:
    print(f"\nstep: {step_id}", flush=True)
    print(f"cwd: {format_cwd(cwd)}", flush=True)
    print(f"command: {format_command(command)}", flush=True)
    returncode = run_process(
        command,
        timeout,
        step_id,
        cwd=cwd,
        env=subprocess_env(env),
    )
    if returncode:
        report_failure(step_id, command, cwd, returncode)
        raise SystemExit(returncode)
    print(f"{step_id} ok", flush=True)


def build_steps(py: str, temp_root: Path) -> list[Step]:
    install_temp = temp_root / "install"
    pipeline_temp = temp_root / "pipeline-out"
    return [
        Step("root.compile", (compile_command(py, temp_root),)),
        Step(
            "root.ruff",
            (
                CommandSpec(
                    [py, "-m", "ruff", "check", ".", "--no-cache", "--config", str(RUFF_CONFIG)]
                ),
            ),
        ),
        Step("root.repo_hygiene", (CommandSpec([py, "scripts/check_repo_hygiene.py"]),)),
        Step(
            "root.tests",
            (pytest_command(py, "-q", extra_env={"SOLVENOTES_TEST_SELF_CHECK_LEVEL": "runtime"}),),
        ),
        Step(
            "metadata.sync",
            (
                CommandSpec([py, "scripts/check_openai_yaml_sync.py"]),
                CommandSpec([py, "scripts/sync_shared_resources.py", "--check"]),
            ),
        ),
        Step(
            "metadata.install",
            (
                CommandSpec(
                    [
                        py,
                        "scripts/install_skill.py",
                        "--all",
                        "--destination",
                        str(install_temp),
                        "--self-check-level",
                        "smoke",
                    ]
                ),
                CommandSpec(
                    [
                        py,
                        "scripts/update_installed_skills.py",
                        "--all",
                        "--destination",
                        str(install_temp),
                        "--self-check-level",
                        "metadata",
                    ]
                ),
                CommandSpec([py, "scripts/update_installed_skills.py", "--all", "--destination", str(install_temp), "--dry-run"]),
            ),
            quick=False,
        ),
        Step("ppt.compile", (compile_command(py, temp_root, cwd=PPT_SKILL),), skill="ppt"),
        Step("ppt.tests", (pytest_command(py, "-q", "tests", cwd=PPT_SKILL),), skill="ppt", quick=False),
        Step("ppt.validator", (CommandSpec([py, "scripts/validate_skill_repo.py"], cwd=PPT_SKILL),), skill="ppt"),
        Step(
            "ppt.pipeline",
            (
                CommandSpec([py, "scripts/extract_pptx_text.py", "examples/sample-course/raw/sample_course.pptx", "--out", str(temp_root / "sample_course_extracted.md")], cwd=PPT_SKILL),
                CommandSpec([py, "scripts/clean_latex_from_ppt.py", "examples/sample-course/extracted/sample_course_extracted.md", "--unicode-math", "--out", str(temp_root / "sample_course_cleaned.md")], cwd=PPT_SKILL),
                CommandSpec([py, "scripts/ppt_to_obsidian_pipeline.py", "--config", "skill-config.example.yaml", "--output-dir", str(pipeline_temp)], cwd=PPT_SKILL),
                CommandSpec([py, "scripts/check_obsidian_links.py", "examples/sample-course/notes"], cwd=PPT_SKILL),
                CommandSpec([py, "scripts/check_course_notes.py", "examples/sample-course/notes"], cwd=PPT_SKILL),
            ),
            skill="ppt",
            quick=False,
        ),
        Step("vault.compile", (compile_command(py, temp_root, cwd=VAULT_SKILL),), skill="vault"),
        Step("vault.tests", (pytest_command(py, "-q", "tests", cwd=VAULT_SKILL),), skill="vault", quick=False),
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
        Step("web.compile", (compile_command(py, temp_root, cwd=WEB_SKILL),), skill="web"),
        Step("web.tests", (pytest_command(py, "-q", "tests", cwd=WEB_SKILL),), skill="web", quick=False),
        Step("web.validator", (CommandSpec([py, "scripts/validate_skill.py"], cwd=WEB_SKILL),), skill="web"),
        Step(
            "web.pipeline",
            (
                CommandSpec([py, "scripts/collect_web_sources.py", "examples/sample-web-course/index.html", "--out", str(temp_root / "web_course_source_manifest.md")], cwd=WEB_SKILL),
                CommandSpec([py, "scripts/create_web_notes.py", "https://example.com/papers/Zhu_From_Noise_Modeling_CVPR_2016_paper.pdf", "--notes-dir", str(temp_root / "web-notes"), "--dry-run"], cwd=WEB_SKILL),
            ),
            skill="web",
            quick=False,
        ),
        Step("notes.compile", (compile_command(py, temp_root, cwd=NOTES_PPT_SKILL),), skill="notes"),
        Step("notes.tests", (pytest_command(py, "-q", "tests", cwd=NOTES_PPT_SKILL),), skill="notes", quick=False),
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
                        str(temp_root / "scientific_deck_brief.md"),
                        "--title",
                        "Blind Image Denoising",
                        "--mode",
                        "paper-reading",
                    ],
                    cwd=NOTES_PPT_SKILL,
                ),
                CommandSpec(
                    [
                        py,
                        "scripts/build_scientific_deck.py",
                        str(temp_root / "scientific_deck_brief.md"),
                        "--out",
                        str(temp_root / "scientific_deck.pptx"),
                    ],
                    cwd=NOTES_PPT_SKILL,
                ),
                CommandSpec(
                    [
                        py,
                        "scripts/verify_pptx.py",
                        str(temp_root / "scientific_deck.pptx"),
                        "--expected-slides",
                        "15",
                        "--expected-title",
                        "Blind Image Denoising",
                        "--expected-width-inches",
                        "13.333",
                        "--expected-height-inches",
                        "7.5",
                        "--render",
                    ],
                    cwd=NOTES_PPT_SKILL,
                ),
            ),
            skill="notes",
            quick=False,
        ),
        Step("algorithm-job.compile", (compile_command(py, temp_root, cwd=ALGORITHM_JOB_SKILL),), skill="algorithm-job"),
        Step("algorithm-job.tests", (pytest_command(py, "-q", "tests", cwd=ALGORITHM_JOB_SKILL),), skill="algorithm-job", quick=False),
        Step("algorithm-job.validator", (CommandSpec([py, "scripts/validate_skill.py"], cwd=ALGORITHM_JOB_SKILL),), skill="algorithm-job"),
        Step("solvenotes-vault.compile", (compile_command(py, temp_root, cwd=SOLVENOTES_VAULT_SKILL),), skill="solvenotes-vault"),
        Step("solvenotes-vault.tests", (pytest_command(py, "-q", "tests", cwd=SOLVENOTES_VAULT_SKILL),), skill="solvenotes-vault", quick=False),
        Step("solvenotes-vault.validator", (CommandSpec([py, "scripts/validate_skill.py"], cwd=SOLVENOTES_VAULT_SKILL),), skill="solvenotes-vault"),
    ]


def selected_steps(steps: list[Step], quick: bool, skill: str | None) -> list[Step]:
    if skill is not None:
        skill_key = normalize_skill(skill)
        return [step for step in steps if step.skill == skill_key and (step.quick or not quick)]
    return [step for step in steps if step.quick or not quick]


def validation_python() -> str:
    """Choose the interpreter used by child validation commands."""
    override = os.environ.get(PYTHON_BIN_OVERRIDE, "").strip()
    if not override:
        return sys.executable
    candidate = Path(override).expanduser()
    if not candidate.is_file():
        raise SystemExit(f"{PYTHON_BIN_OVERRIDE} is not a file: {candidate}")
    if not os.access(candidate, os.X_OK):
        raise SystemExit(f"{PYTHON_BIN_OVERRIDE} is not executable: {candidate}")
    return str(candidate)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="run compile, root tests, repo hygiene, metadata sync, and skill validators; skip skill tests and sample pipeline/deck smoke runs",
    )
    parser.add_argument(
        "--skill",
        metavar="NAME",
        help=f"run validation stages only for one skill. Valid names and aliases: {format_skill_choices()}",
    )
    parser.add_argument("--list-steps", action="store_true", help="list stable validation step ids and exit")
    args = parser.parse_args(argv)
    try:
        skill = normalize_skill(args.skill)
    except ValueError as exc:
        parser.error(str(exc))

    py = validation_python()
    with tempfile.TemporaryDirectory(prefix="codex-obsidian-skills-validate-") as temporary:
        steps = build_steps(py, Path(temporary))

        if args.list_steps:
            print("preflight.doctor")
            for step in steps:
                print(step.step_id)
            return 0

        profile = "tool-quick" if args.quick else "tool-full"
        run_command(
            "preflight.doctor",
            [
                py,
                str(ROOT / "scripts" / "doctor.py"),
                "--python-bin",
                py,
                "--skills-root",
                str(ROOT),
                "--profile",
                profile,
                "--strict",
            ],
            ROOT,
        )

        for step in selected_steps(steps, quick=args.quick, skill=skill):
            for command in step.commands:
                run_command(step.step_id, command.command, command.cwd, env=command.env)

    suffix = " quick" if args.quick else ""
    skill_text = f" skill={skill}" if skill else ""
    print(f"\nvalidate_all{suffix}{skill_text} ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
