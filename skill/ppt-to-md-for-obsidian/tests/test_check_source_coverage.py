from __future__ import annotations

from pathlib import Path
import subprocess
import sys


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_source_coverage.py"


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

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-root",
            str(source_root),
            "--notes-root",
            str(notes_root),
            "--mapping",
            "课程A=课程A笔记",
        ],
        text=True,
        capture_output=True,
        check=False,
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

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-root",
            str(source_root),
            "--notes-root",
            str(notes_root),
            "--mapping",
            "课程A=课程A笔记",
        ],
        text=True,
        capture_output=True,
        check=False,
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

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-root",
            str(source_root),
            "--notes-root",
            str(notes_root),
            "--mapping",
            "课程A=课程A笔记",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "RESIDUAL_MANUAL_REVIEW_MARKER" in result.stdout
