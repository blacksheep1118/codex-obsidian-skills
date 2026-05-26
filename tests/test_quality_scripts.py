from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run_command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], cwd=ROOT, text=True, capture_output=True)


def test_vault_quality_accepts_clean_fixture():
    result = run_command("skill/obsidian-vault-organizer/scripts/check_vault_quality.py", "fixtures/vault-clean")

    assert result.returncode == 0
    assert "vault_quality_issues 0" in result.stdout


def test_vault_quality_reports_common_issues(tmp_path: Path):
    vault = tmp_path / "vault"
    shutil.copytree(ROOT / "fixtures" / "vault-quality-issues", vault)
    (vault / "conflict.md").write_text("# Conflict\n\n<<<<<<< HEAD\nold\n=======\nnew\n>>>>>>> branch\n", encoding="utf-8")

    result = run_command("skill/obsidian-vault-organizer/scripts/check_vault_quality.py", str(vault))

    assert result.returncode == 1
    assert "CONFLICT_MARKER" in result.stdout
    assert "EMPTY_FILE" in result.stdout
    assert "UNBALANCED_MATH" in result.stdout
    assert "TEMPLATE_RESIDUE" in result.stdout


def test_course_note_checker_accepts_sample_notes():
    result = run_command("skill/ppt-to-md-for-obsidian/scripts/check_course_notes.py", "skill/ppt-to-md-for-obsidian/examples/sample-course/notes")

    assert result.returncode == 0
    assert "course_note_issues 0" in result.stdout


def test_course_note_checker_requires_review_pages(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "00_课程总览.md").write_text("# 课程总览\n\n- [[01_主题]]\n", encoding="utf-8")
    (notes / "01_主题.md").write_text("# 主题\n\n正文。\n", encoding="utf-8")

    result = run_command("skill/ppt-to-md-for-obsidian/scripts/check_course_notes.py", str(notes))

    assert result.returncode == 1
    assert "MISSING_REVIEW_PAGE" in result.stdout
    assert "MISSING_REVIEW_LINK" in result.stdout
