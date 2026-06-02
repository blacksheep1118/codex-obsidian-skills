from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def run_command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


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


def test_course_note_checker_accepts_course_prefixed_review_pages(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "00_游戏数值策划学习总览.md").write_text(
        "# 游戏数值策划学习总览\n\n"
        "- [[游戏数值策划知识点详细版_含公式]]\n"
        "- [[游戏数值策划知识点精简复习版_含公式]]\n",
        encoding="utf-8",
    )
    (notes / "01_主题.md").write_text("# 主题\n\n正文。\n", encoding="utf-8")
    (notes / "游戏数值策划知识点详细版_含公式.md").write_text("# 详细\n\n核心机制。\n", encoding="utf-8")
    (notes / "游戏数值策划知识点精简复习版_含公式.md").write_text("# 精简\n\n核心公式。\n", encoding="utf-8")

    result = run_command("skill/ppt-to-md-for-obsidian/scripts/check_course_notes.py", str(notes))

    assert result.returncode == 0
    assert "course_note_issues 0" in result.stdout


def test_course_note_checker_strict_depth_reports_thin_generic_notes(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "00_课程总览.md").write_text(
        "# 课程总览\n\n- [[知识点详细版_含公式]]\n- [[知识点精简复习版_含公式]]\n",
        encoding="utf-8",
    )
    (notes / "01_主题.md").write_text("# 主题\n\n正文太少。\n", encoding="utf-8")
    (notes / "知识点详细版_含公式.md").write_text("# 详细\n\n例题模板：先写定义再套公式。\n", encoding="utf-8")
    (notes / "知识点精简复习版_含公式.md").write_text("# 精简\n\n核心公式。\n", encoding="utf-8")

    result = run_command(
        "skill/ppt-to-md-for-obsidian/scripts/check_course_notes.py",
        "--strict-depth",
        "--min-chapter-lines",
        "5",
        "--min-detailed-lines",
        "5",
        str(notes),
    )

    assert result.returncode == 1
    assert "THIN_CHAPTER_NOTE" in result.stdout
    assert "THIN_DETAILED_REVIEW" in result.stdout
    assert "GENERIC_TEMPLATE_RESIDUE" in result.stdout


def test_course_note_checker_allows_single_exam_review_with_audit(tmp_path: Path):
    notes = tmp_path / "notes"
    notes.mkdir()
    exam_body = "\n".join(f"- 知识点 {index}：定义、公式、例题和易错点。" for index in range(1, 6))
    (notes / "00_机器学习课程总览.md").write_text(
        "# 机器学习课程总览\n\n- [[机器学习考试复习笔记]]\n",
        encoding="utf-8",
    )
    (notes / "机器学习考试复习笔记.md").write_text(f"# 机器学习考试复习笔记\n\n{exam_body}\n", encoding="utf-8")
    (notes / "99_内容覆盖审查.md").write_text("# 内容覆盖审查\n\n- 已核对来源。\n", encoding="utf-8")
    (notes / "source_manifest.md").write_text("# Source Manifest\n\n- source.pdf\n", encoding="utf-8")

    result = run_command(
        "skill/ppt-to-md-for-obsidian/scripts/check_course_notes.py",
        "--strict-depth",
        "--allow-exam-review",
        "--require-coverage-audit",
        "--min-exam-review-lines",
        "5",
        str(notes),
    )

    assert result.returncode == 0
    assert "course_note_issues 0" in result.stdout
