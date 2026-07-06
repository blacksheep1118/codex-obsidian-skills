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


def run_checker(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, str(root)],
        text=True,
        encoding="utf-8",
        errors="replace",
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


def test_check_course_notes_skip_dir_ignores_non_course_index_dirs(tmp_path: Path) -> None:
    course = tmp_path / "课程"
    write_minimal_course(course, "正文。")
    write(course / "概念索引" / "index.md", "# Index\n\nTODO\n")
    write(course / "生成审查" / "empty.md", "")

    without_skip = run_checker(course)
    assert without_skip.returncode == 1
    assert "TEMPLATE_RESIDUE" in without_skip.stdout
    assert "EMPTY_FILE" in without_skip.stdout

    with_skip = run_checker(course, "--skip-dir", "概念索引", "--skip-dir", "生成审查")
    assert with_skip.returncode == 0, with_skip.stdout + with_skip.stderr
    assert "course_note_issues 0" in with_skip.stdout
