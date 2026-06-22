from __future__ import annotations

from pathlib import Path
import subprocess
import sys


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_course_notes.py"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_minimal_course(root: Path, table: str) -> None:
    write(
        root / "00_课程总览.md",
        "# 课程总览\n\n[[知识点详细版_含公式]]\n[[知识点精简复习版_含公式]]\n",
    )
    write(root / "知识点详细版_含公式.md", "# 详细版\n\n内容。\n")
    write(root / "知识点精简复习版_含公式.md", "# 精简版\n\n内容。\n")
    write(root / "01_导论.md", "# 导论\n\n" + table + "\n")


def run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_check_course_notes_reports_broken_markdown_table(tmp_path: Path) -> None:
    course = tmp_path / "课程"
    write_minimal_course(
        course,
        "\n".join(
            [
                "| 正则式 | 语言 |",
                "|---|---|",
                "| `a|b` | `{a,b}` |",
            ]
        ),
    )

    result = run_checker(course)

    assert result.returncode == 1
    assert "BROKEN_TABLE" in result.stdout


def test_check_course_notes_accepts_escaped_pipes_and_plain_wiki_links(tmp_path: Path) -> None:
    course = tmp_path / "课程"
    write_minimal_course(
        course,
        "\n".join(
            [
                "| 正则式 | 对应笔记 |",
                "|---|---|",
                "| `a\\|b` | [[课程/01_导论]] |",
            ]
        ),
    )

    result = run_checker(course)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "course_note_issues 0" in result.stdout
