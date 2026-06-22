from __future__ import annotations

from pathlib import Path
import subprocess
import sys


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_source_coverage.py"


def run_checker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_check_source_coverage_passes_with_mapping_and_examples(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    write(source_root / "课程A" / "ch1.pdf", "fake pdf")
    write(
        notes_root / "课程A笔记" / "source_manifest.md",
        "| source | note |\n|---|---|\n| `ch1.pdf` | `01_导论.md` |\n",
    )
    write(
        notes_root / "课程A笔记" / "99_内容覆盖审查.md",
        "| source | status |\n|---|---|\n| `ch1.pdf` | 已写入 |\n",
    )
    write(
        notes_root / "课程A笔记" / "01_导论.md",
        "\n".join(
            [
                "# 导论",
                "",
                "| 知识点 | 例题/辅助题 | 来源 |",
                "|---|---|---|",
                "| 定义 | 源资料例题：例 1。 | 源资料：（/课程A/ch1）ch1.pdf p.1 |",
                "",
                "## PPT/PDF 页级补充索引",
                "",
                "- 来源：`课程A/ch1.pdf`，页/slide：1；主题：导论；生成：PPT/PDF 未提供独立可抽取例题；补充题（/课程A/ch1 p.1）：解释导论。",
            ]
        ),
    )
    write(
        notes_root / "非目标目录" / "bad.md",
        "## PPT/PDF 页级补充索引\n\n- 来源：`x`，页/slide：1；主题：x；补充题：需复核。\n",
    )

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--mapping",
        "课程A=课程A笔记",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "course_source_files 1" in result.stdout
    assert "coverage_evidence_issues 0" in result.stdout


def test_check_source_coverage_reports_missing_mapping_and_bad_example(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    write(source_root / "课程A" / "ch1.pdf", "fake pdf")
    write(notes_root / "课程A笔记" / "source_manifest.md", "| source |\n|---|\n| `other.pdf` |\n")
    write(
        notes_root / "课程A笔记" / "01_导论.md",
        "\n".join(
            [
                "# 导论",
                "",
                "## PPT/PDF 页级补充索引",
                "",
                "- 来源：`课程A/ch1.pdf`，页/slide：1；主题：导论；补充题：解释导论。",
            ]
        ),
    )

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--mapping",
        "课程A=课程A笔记",
    )

    assert result.returncode == 1
    assert "MISSING_SOURCE_MAPPING" in result.stdout
    assert "BAD_SUPPLEMENT_EXAMPLE" in result.stdout


def test_check_source_coverage_reports_manual_review_residue(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    write(source_root / "课程A" / "ch1.pdf", "fake pdf")
    write(notes_root / "课程A笔记" / "source_manifest.md", "`ch1.pdf`\n")
    write(
        notes_root / "课程A笔记" / "01_导论.md",
        "\n".join(
            [
                "# 导论",
                "",
                "| 知识点 | 例题/辅助题 | 来源 |",
                "|---|---|---|",
                "| 定义 | 源资料例题：例 1。 | 源资料：（/课程A/ch1 p.1） |",
                "",
                "## PPT/PDF 页级补充索引",
                "",
                "- 来源：`课程A/ch1.pdf`，页/slide：1；主题：导论；源资料例题：例 1（/课程A/ch1 p.1）；需复核。",
            ]
        ),
    )

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--mapping",
        "课程A=课程A笔记",
    )

    assert result.returncode == 1
    assert "RESIDUAL_MANUAL_REVIEW_MARKER" in result.stdout


def test_check_source_coverage_reports_chapter_mismatch_in_tables_and_notes(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    write(source_root / "数学模型" / "第八章 离散模型8.1.pdf", "fake pdf")
    write(
        notes_root / "数学模型" / "source_manifest.md",
        "| 源文件 | 对应笔记 |\n"
        "|---|---|\n"
        "| `数学模型/第八章 离散模型8.1.pdf` | [[数学模型/08_第五章_微分方程模型_2]] |\n",
    )
    write(
        notes_root / "数学模型" / "99_内容覆盖审查.md",
        "| 源文件 | 对应笔记 |\n"
        "|---|---|\n"
        "| `数学模型/第八章 离散模型8.1.pdf` | [[数学模型/08_第五章_微分方程模型_2]] |\n",
    )
    write(
        notes_root / "数学模型" / "08_第五章_微分方程模型_2.md",
        "\n".join(
            [
                "# 数学模型：第五章 微分方程模型（2）",
                "",
                "| 知识点 | 例题/辅助题 | 来源 |",
                "|---|---|---|",
                "| 层次分析法 | 源资料例题：例 1。 | 源资料：（/数学模型/ch8）第八章 离散模型8.1.pdf p.7 |",
            ]
        ),
    )

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--mapping",
        "数学模型=数学模型",
        "--require-course-prefixed-source-refs",
    )

    assert result.returncode == 1
    assert "CHAPTER_MISMATCH_SOURCE_LINK" in result.stdout
    assert "CHAPTER_MISMATCH_NOTE_SOURCE" in result.stdout


def test_check_source_coverage_requires_course_prefixed_source_refs(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    write(source_root / "编译原理" / "lecture 1.pptx", "fake pptx")
    write(
        notes_root / "编译原理" / "source_manifest.md",
        "| source | note |\n|---|---|\n| `lecture 1.pptx` | [[编译原理/01_词法分析]] |\n",
    )
    write(
        notes_root / "编译原理" / "99_内容覆盖审查.md",
        "| source | note |\n|---|---|\n| `lecture 1.pptx` | [[编译原理/01_词法分析]] |\n",
    )
    write(
        notes_root / "编译原理" / "01_词法分析.md",
        "| 知识点 | 例题/辅助题 | 来源 |\n"
        "|---|---|---|\n"
        "| token | 源资料例题：识别 token。 | 源资料：（/编译原理/lecture 1 p.1） |\n",
    )

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--mapping",
        "编译原理=编译原理",
        "--require-course-prefixed-source-refs",
    )

    assert result.returncode == 1
    assert "NONCANONICAL_SOURCE_REF" in result.stdout


def test_check_source_coverage_does_not_treat_lecture_subparts_as_chapter_conflicts(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    write(source_root / "编译原理" / "lecture 4b.pptx", "fake pptx")
    write(
        notes_root / "编译原理" / "source_manifest.md",
        "| source | note |\n|---|---|\n| `编译原理/lecture 4b.pptx` | [[编译原理/08_自顶向下语法分析_LL1与FIRST_FOLLOW]] |\n",
    )
    write(
        notes_root / "编译原理" / "99_内容覆盖审查.md",
        "| source | note |\n|---|---|\n| `编译原理/lecture 4b.pptx` | [[编译原理/08_自顶向下语法分析_LL1与FIRST_FOLLOW]] |\n",
    )
    write(
        notes_root / "编译原理" / "08_自顶向下语法分析_LL1与FIRST_FOLLOW.md",
        "\n".join(
            [
                "# 第4讲B：自顶向下语法分析、LL(1) 与 FIRST/FOLLOW",
                "",
                "| 知识点 | 例题/辅助题 | 来源 |",
                "|---|---|---|",
                "| FIRST | 源资料例题：计算 FIRST。 | 源资料：（/编译原理/lecture 4b p.1）lecture 4b.pptx |",
            ]
        ),
    )

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--mapping",
        "编译原理=编译原理",
        "--require-course-prefixed-source-refs",
    )

    assert result.returncode == 0, result.stdout + result.stderr
