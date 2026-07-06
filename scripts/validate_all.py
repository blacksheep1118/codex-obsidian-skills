#!/usr/bin/env python3
"""Run the full repository validation suite used by CI."""

from __future__ import annotations

import os
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


def format_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def format_cwd(cwd: Path) -> str:
    try:
        return str(cwd.relative_to(ROOT)) if cwd != ROOT else "."
    except ValueError:
        return str(cwd)


def report_failure(command: list[str], cwd: Path, returncode: int | str) -> None:
    print("\nvalidation command failed", file=sys.stderr, flush=True)
    print(f"cwd: {cwd}", file=sys.stderr, flush=True)
    print(f"command: {format_command(command)}", file=sys.stderr, flush=True)
    print(f"return code: {returncode}", file=sys.stderr, flush=True)


def run(command: list[str], cwd: Path = ROOT, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> None:
    print(f"\n:: {format_cwd(cwd)}$ {format_command(command)}", flush=True)
    try:
        subprocess.run(command, cwd=cwd, check=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        report_failure(command, cwd, f"timeout after {timeout}s")
        raise SystemExit(124) from None
    except subprocess.CalledProcessError as exc:
        report_failure(command, cwd, exc.returncode)
        raise SystemExit(exc.returncode) from None


def main() -> int:
    py = sys.executable

    run([py, "-m", "compileall", "scripts"])
    run([py, "scripts/check_openai_yaml_sync.py"])
    run([py, "scripts/sync_shared_resources.py", "--check"])
    run([py, "scripts/install_skill.py", "--all", "--dry-run", "--self-check"])
    run([py, "scripts/install_skill.py", "--all", "--destination", str(INSTALL_TMP), "--self-check"])
    run([py, "scripts/update_installed_skills.py", "--all", "--destination", str(INSTALL_TMP), "--dry-run", "--prune"])

    if (ROOT / "tests").exists():
        run([py, "-m", "pytest", "tests"])

    run([py, "-m", "compileall", "scripts"], cwd=PPT_SKILL)
    run([py, "-m", "pytest", "tests"], cwd=PPT_SKILL)
    run([py, "scripts/validate_skill_repo.py"], cwd=PPT_SKILL)
    run([py, "scripts/extract_pptx_text.py", "examples/sample-course/raw/sample_course.pptx", "--out", str(TMP / "sample_course_extracted.md")], cwd=PPT_SKILL)
    run([py, "scripts/clean_latex_from_ppt.py", "examples/sample-course/extracted/sample_course_extracted.md", "--unicode-math", "--out", str(TMP / "sample_course_cleaned.md")], cwd=PPT_SKILL)
    run([py, "scripts/ppt_to_obsidian_pipeline.py", "--config", "skill-config.example.yaml", "--output-dir", str(PIPELINE_TMP)], cwd=PPT_SKILL)
    run([py, "scripts/check_obsidian_links.py", "examples/sample-course/notes"], cwd=PPT_SKILL)
    run([py, "scripts/check_course_notes.py", "examples/sample-course/notes"], cwd=PPT_SKILL)

    run([py, "-m", "compileall", "scripts"], cwd=VAULT_SKILL)
    run([py, "-m", "pytest", "tests"], cwd=VAULT_SKILL)
    run([py, "scripts/validate_skill.py"], cwd=VAULT_SKILL)
    run([py, "scripts/check_obsidian_links.py", "../ppt-to-md-for-obsidian/examples/sample-course/notes"], cwd=VAULT_SKILL)
    run([py, "scripts/check_vault_quality.py", "../../fixtures/vault-clean"], cwd=VAULT_SKILL)

    run([py, "-m", "compileall", "scripts"], cwd=WEB_SKILL)
    run([py, "-m", "pytest", "tests"], cwd=WEB_SKILL)
    run([py, "scripts/validate_skill.py"], cwd=WEB_SKILL)
    run(
        [
            py,
            "scripts/collect_web_sources.py",
            "examples/sample-web-course/index.html",
            "--out",
            str(TMP / "web_course_source_manifest.md"),
        ],
        cwd=WEB_SKILL,
    )
    run(
        [
            py,
            "scripts/create_web_notes.py",
            "https://example.com/papers/Zhu_From_Noise_Modeling_CVPR_2016_paper.pdf",
            "--notes-dir",
            str(TMP / "codex-obsidian-skills-web-notes"),
            "--dry-run",
        ],
        cwd=WEB_SKILL,
    )

    run([py, "-m", "compileall", "scripts"], cwd=NOTES_PPT_SKILL)
    run([py, "-m", "pytest", "tests"], cwd=NOTES_PPT_SKILL)
    run([py, "scripts/validate_skill.py"], cwd=NOTES_PPT_SKILL)
    run(
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
    )

    print("\nvalidate_all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
