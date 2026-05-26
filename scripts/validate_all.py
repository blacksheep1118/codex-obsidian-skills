#!/usr/bin/env python3
"""Run the full repository validation suite used by CI."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PPT_SKILL = ROOT / "skill" / "ppt-to-md-for-obsidian"
VAULT_SKILL = ROOT / "skill" / "obsidian-vault-organizer"
WEB_SKILL = ROOT / "skill" / "web-course-notes-for-obsidian"
TMP = Path(tempfile.gettempdir())
INSTALL_TMP = TMP / "codex-obsidian-skills-validate-install"
PIPELINE_TMP = TMP / "codex-obsidian-skills-pipeline-out"


def run(command: list[str], cwd: Path = ROOT) -> None:
    printable = " ".join(command)
    print(f"\n:: {cwd.relative_to(ROOT) if cwd != ROOT else '.'}$ {printable}")
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    py = sys.executable

    run([py, "-m", "compileall", "scripts"])
    run([py, "scripts/check_openai_yaml_sync.py"])
    run([py, "scripts/check_shared_link_checker.py"])
    run([py, "scripts/install_skill.py", "--all", "--dry-run", "--self-check"])
    run([py, "scripts/install_skill.py", "--all", "--destination", str(INSTALL_TMP), "--self-check"])
    run([py, "scripts/update_installed_skills.py", "--all", "--destination", str(INSTALL_TMP), "--dry-run", "--prune"])

    if (ROOT / "tests").exists():
        run([py, "-m", "pytest", "tests"])

    run([py, "-m", "compileall", "scripts"], cwd=PPT_SKILL)
    run([py, "-m", "pytest"], cwd=PPT_SKILL)
    run([py, "scripts/validate_skill_repo.py"], cwd=PPT_SKILL)
    run([py, "scripts/extract_pptx_text.py", "examples/sample-course/raw/sample_course.pptx", "--out", str(TMP / "sample_course_extracted.md")], cwd=PPT_SKILL)
    run([py, "scripts/clean_latex_from_ppt.py", "examples/sample-course/extracted/sample_course_extracted.md", "--unicode-math", "--out", str(TMP / "sample_course_cleaned.md")], cwd=PPT_SKILL)
    run([py, "scripts/ppt_to_obsidian_pipeline.py", "--config", "skill-config.example.yaml", "--output-dir", str(PIPELINE_TMP)], cwd=PPT_SKILL)
    run([py, "scripts/check_obsidian_links.py", "examples/sample-course/notes"], cwd=PPT_SKILL)
    run([py, "scripts/check_course_notes.py", "examples/sample-course/notes"], cwd=PPT_SKILL)

    run([py, "-m", "compileall", "scripts"], cwd=VAULT_SKILL)
    run([py, "scripts/validate_skill.py"], cwd=VAULT_SKILL)
    run([py, "scripts/check_obsidian_links.py", "../ppt-to-md-for-obsidian/examples/sample-course/notes"], cwd=VAULT_SKILL)
    run([py, "scripts/check_vault_quality.py", "../../fixtures/vault-clean"], cwd=VAULT_SKILL)

    run([py, "-m", "compileall", "scripts"], cwd=WEB_SKILL)
    run([py, "-m", "pytest"], cwd=WEB_SKILL)
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

    print("\nvalidate_all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
