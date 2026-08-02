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


def test_check_source_coverage_does_not_infer_owner_from_chapter_ordinals(tmp_path: Path) -> None:
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
    assert "STRUCTURAL: MANIFEST_TARGET_OWNER_MISMATCH" in result.stdout
    assert "CHAPTER_MISMATCH_SOURCE_LINK" not in result.stdout
    assert "CHAPTER_MISMATCH_NOTE_SOURCE" not in result.stdout


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
        "---\nsource_files:\n  - \"编译原理/lecture 4b.pptx\"\n---\n"
        + "\n".join(
            [
                "# 第4讲B：自顶向下语法分析、LL(1) 与 FIRST/FOLLOW",
                "",
                "| 知识点 | 例题/辅助题 | 来源 |",
                "|---|---|---|",
                "| FIRST | 源资料例题：计算 FIRST。 | 源资料：`编译原理/lecture 4b.pptx` p.1 |",
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


def test_strict_source_coverage_keeps_manifest_audit_and_note_ownership_separate(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    write(source_root / "课程A" / "ch1.pdf", "fake pdf")
    write(source_root / "课程A" / "ch2.pdf", "fake pdf")
    write(
        notes_root / "课程A" / "99_内容覆盖审查.md",
        "| source | note |\n|---|---|\n| `课程A/ch1.pdf` | [[课程A/01_导论]] |\n",
    )
    write(
        notes_root / "课程A" / "01_导论.md",
        "---\nsource_files:\n  - \"课程A/ch1.pdf\"\n---\n# 导论\n\n源资料例题：例 1（/课程A/ch1 p.1）。\n",
    )

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--mapping",
        "课程A=课程A",
        "--require-four-way-source-coverage",
    )

    assert result.returncode == 1
    assert "MISSING_SOURCE_MANIFEST" in result.stdout
    assert "MISSING_COVERAGE_AUDIT_MAPPING" in result.stdout
    assert "MISSING_NOTE_SOURCE_OWNERSHIP" in result.stdout


def test_strict_mode_discovers_cs231n_and_reconciles_unmapped_source_dirs(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    write(source_root / "cs231n" / "lecture_1_part_1.pdf", "fake pdf")
    write(source_root / "orphan" / "lecture.pdf", "fake pdf")
    write(
        notes_root / "cs231n" / "source_manifest.md",
        "| source | note |\n|---|---|\n| `cs231n/lecture_1_part_1.pdf` | [[cs231n/01_intro]] |\n",
    )
    write(
        notes_root / "cs231n" / "99_内容覆盖审查.md",
        "| source | note |\n|---|---|\n| `cs231n/lecture_1_part_1.pdf` | [[cs231n/01_intro]] |\n",
    )
    write(
        notes_root / "cs231n" / "01_intro.md",
        "---\nsource_files:\n  - \"cs231n/lecture_1_part_1.pdf\"\n---\n# Intro\n\n源资料例题：例 1（/cs231n/lecture_1_part_1 p.1）。\n",
    )

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--strict",
    )

    assert result.returncode == 1
    assert "course_source_files 1" in result.stdout
    assert "UNMAPPED_SOURCE_DIR" in result.stdout
    assert "MISSING_SOURCE_MANIFEST" not in result.stdout
    assert "MISSING_NOTE_SOURCE_OWNERSHIP" not in result.stdout


def test_strict_mode_accepts_explicit_full_mapping_for_alias_directories(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    source_name = "All-in-One : Unified Image Restoration"
    notes_name = "all-in-one"
    source_file = f"{source_name}/lecture.pdf"
    write(source_root / source_name / "lecture.pdf", "fake pdf")
    write(
        notes_root / notes_name / "source_manifest.md",
        f"| source | note |\n|---|---|\n| `{source_file}` | [[{notes_name}/01_intro]] |\n",
    )
    write(
        notes_root / notes_name / "99_内容覆盖审查.md",
        f"| source | note |\n|---|---|\n| `{source_file}` | [[{notes_name}/01_intro]] |\n",
    )
    write(
        notes_root / notes_name / "01_intro.md",
        f"---\nsource_files:\n  - \"{source_file}\"\n---\n"
        f"# Intro\n\n源资料例题：例 1（/{source_name}/lecture p.1）。\n",
    )

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--strict",
        "--mapping",
        f"{source_name}={notes_name}",
    )

    assert result.returncode == 1
    assert "source_dir_reconciliation_issues 0" in result.stdout
    assert "structural_issues 0" in result.stdout
    assert "MANUAL_REVIEW_REQUIRED: MISSING_BODY_SOURCE_EVIDENCE" in result.stdout


def test_strict_mode_excludes_standalone_note_systems_from_reconciliation(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    source_root.mkdir()
    for name in ("概念索引", "模板", "游戏数值策划", "科研方法论"):
        write(
            notes_root / name / "99_内容覆盖审查.md",
            "---\n"
            "note_type: coverage_audit\n"
            "source_files: []\n"
            "---\n"
            "本目录在本地项目规范中属于笔记侧独立体系，当前根目录没有可确定的一一对应 PPT/PDF 课件目录。\n",
        )

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--strict",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "source_dir_reconciliation_issues 0" in result.stdout


def test_default_scan_ignores_scripts_and_caches_but_can_include_them(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    write(source_root / "课程A" / "ch1.pdf", "fake pdf")
    for name in ("scripts", ".pytest_cache"):
        write(notes_root / "课程A" / name / "bad.md", "需复核\n")
    write(notes_root / "课程A" / "source_manifest.md", "`ch1.pdf`\n")
    write(notes_root / "课程A" / "99_内容覆盖审查.md", "`ch1.pdf`\n")
    write(
        notes_root / "课程A" / "01_intro.md",
        "# Intro\n\n源资料例题：例 1（/课程A/ch1 p.1）。\n",
    )

    base_args = (
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--mapping",
        "课程A=课程A",
    )
    result = run_checker(*base_args)
    assert result.returncode == 0, result.stdout + result.stderr

    included = run_checker(*base_args, "--include-ignored")
    assert included.returncode == 1
    assert "RESIDUAL_MANUAL_REVIEW_MARKER" in included.stdout


def test_paper_source_ownership_checks_five_notes_and_undeclared_body_sources(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    for index in range(1, 6):
        write(source_root / "papers" / f"paper_{index}.pdf", "fake pdf")
        write(
            notes_root / "papers" / f"paper_{index}.md",
            "---\n"
            "note_type: paper_note\n"
            "source_files:\n"
            f"  - \"papers/paper_{index}.pdf\"\n"
            "---\n"
            f"# Paper {index}\n",
        )

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--check-paper-source-ownership",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "paper_source_ownership_issues 0" in result.stdout

    write(
        notes_root / "papers" / "paper_1.md",
        (notes_root / "papers" / "paper_1.md").read_text(encoding="utf-8")
        + "参见 `papers/paper_2.pdf`。\n",
    )
    broken = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--check-paper-source-ownership",
    )
    assert broken.returncode == 1
    assert "PAPER_SOURCE_NOT_DECLARED" in broken.stdout


def test_adjacent_source_parts_require_explicit_ownership_evidence(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    write(source_root / "course" / "lecture_1_part_1.pdf", "fake pdf")
    write(source_root / "course" / "lecture_1_part_2.pdf", "fake pdf")
    for name in ("source_manifest.md", "99_内容覆盖审查.md"):
        write(
            notes_root / "course" / name,
            "| source | note |\n|---|---|\n"
            "| `course/lecture_1_part_1.pdf` | [[course/01_intro]] |\n"
            "| `course/lecture_1_part_2.pdf` | [[course/01_intro]] |\n",
        )
    write(
        notes_root / "course" / "01_intro.md",
        "---\nsource_files:\n  - \"course/lecture_1_part_1.pdf\"\n---\n# Intro\n\n源资料例题：例 1（/course/lecture_1_part_1 p.1）。\n",
    )
    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--mapping",
        "course=course",
        "--require-four-way-source-coverage",
        "--require-adjacent-source-evidence",
    )
    assert result.returncode == 1
    assert "MISSING_ADJACENT_SOURCE_EVIDENCE" in result.stdout


def test_source_coverage_rejects_mapping_paths_outside_roots(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    source_root.mkdir()
    notes_root.mkdir()

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--mapping",
        "../outside=../other",
    )

    assert result.returncode == 1
    assert "MAPPING_SOURCE_OUTSIDE_ROOT" in result.stdout
    assert "MAPPING_NOTES_OUTSIDE_ROOT" in result.stdout


def test_paper_source_ownership_rejects_paths_outside_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    outside = tmp_path / "outside.pdf"
    write(source_root / "papers" / "paper.pdf", "fake pdf")
    write(outside, "outside pdf")
    write(
        notes_root / "papers" / "paper.md",
        "---\n"
        "note_type: paper_note\n"
        "source_files:\n"
        "  - ../outside.pdf\n"
        f"  - {outside}\n"
        "---\n"
        "# Paper\n\nSee `../outside.pdf`.\n",
    )

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--check-paper-source-ownership",
    )

    assert result.returncode == 1
    assert "PAPER_SOURCE_OUTSIDE_ROOT" in result.stdout


def test_source_coverage_reports_source_symlink_outside_root(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    outside = tmp_path / "outside.pdf"
    write(outside, "outside")
    (source_root / "course").mkdir(parents=True)
    (source_root / "course" / "external.pdf").symlink_to(outside)
    write(notes_root / "course" / "source_manifest.md", "`course/external.pdf`\n")
    write(notes_root / "course" / "99_内容覆盖审查.md", "`course/external.pdf`\n")

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--mapping",
        "course=course",
    )

    assert result.returncode == 1
    assert "SOURCE_SYMLINK_OUTSIDE_ROOT" in result.stdout


def test_real_notes_adapter_missing_page_evidence_is_manual_review_not_full_coverage(tmp_path: Path) -> None:
    """Mirror the current course-note shape without changing the real notes repo."""

    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    source = "编译原理/lecture 4b.pptx"
    write(source_root / source, "fake pptx")
    for name in ("source_manifest.md", "99_内容覆盖审查.md"):
        write(
            notes_root / "编译原理" / name,
            f"| 源文件 | 对应笔记 |\n|---|---|\n| `{source}` | [[编译原理/08_自顶向下语法分析_LL1与FIRST_FOLLOW]] |\n",
        )
    write(
        notes_root / "编译原理" / "08_自顶向下语法分析_LL1与FIRST_FOLLOW.md",
        "---\n"
        "course: 编译原理\n"
        "source_files:\n"
        f"  - {source}\n"
        "---\n"
        "# 第4讲B：自顶向下语法分析、LL(1) 与 FIRST/FOLLOW\n\n"
        f"对应源资料：`{source}`。本页保留文本抽取内容，但没有页或 slide 定位。\n"
        "本页的例题来自课程内容。\n",
    )

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--mapping",
        "编译原理=编译原理",
        "--strict",
        "--require-course-prefixed-source-refs",
    )

    assert result.returncode == 1
    assert "MANUAL_REVIEW_REQUIRED: MISSING_BODY_SOURCE_EVIDENCE" in result.stdout
    assert "structural_issues 0" in result.stdout
    assert "manual_review_required_issues" in result.stdout
    assert "fully covered" not in result.stdout.lower()


def test_real_notes_adapter_chinese_source_topic_is_not_a_false_owner_failure(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    source = "可计算性理论/第一讲 导引 +（有穷状态自动机）.ppt"
    write(source_root / source, "fake ppt")
    for name in ("source_manifest.md", "99_内容覆盖审查.md"):
        write(
            notes_root / "可计算性理论" / name,
            f"| 源文件 | 对应笔记 |\n|---|---|\n| `{source}` | [[可计算性理论/01_导引与有穷状态自动机]] |\n",
        )
    write(
        notes_root / "可计算性理论" / "01_导引与有穷状态自动机.md",
        "---\n"
        "source_files:\n"
        f"  - {source}\n"
        "---\n"
        "# 第1讲：导引与有穷状态自动机\n\n"
        f"对应源资料：`{source}`，p.1。\n"
        "源资料例题：例 1（/可计算性理论/第一讲 p.1）。\n",
    )

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--mapping",
        "可计算性理论=可计算性理论",
        "--strict",
        "--require-course-prefixed-source-refs",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "SOURCE_TOPIC_OWNER_MISMATCH" not in result.stdout
    assert "source_topic_owner_unproven" not in result.stdout


def test_real_notes_adapter_wrong_frontmatter_owner_remains_structural_fail(tmp_path: Path) -> None:
    source_root = tmp_path / "sources"
    notes_root = tmp_path / "notes"
    source = "课程A/03_概率模型.pdf"
    target = "课程A/03_线性代数"
    write(source_root / source, "fake pdf")
    for name in ("source_manifest.md", "99_内容覆盖审查.md"):
        write(
            notes_root / "课程A" / name,
            f"| 源文件 | 对应笔记 |\n|---|---|\n| `{source}` | [[{target}]] |\n",
        )
    write(
        notes_root / "课程A" / "03_线性代数.md",
        "---\n"
        "source_files:\n"
        "  - 课程A/03_错误来源.pdf\n"
        "---\n"
        "# 03_线性代数\n\n"
        f"对应源资料：`{source}`，p.1。\n"
        "源资料例题：例 1（/课程A/03 p.1）。\n",
    )

    result = run_checker(
        "--source-root",
        str(source_root),
        "--notes-root",
        str(notes_root),
        "--mapping",
        "课程A=课程A",
        "--strict",
        "--require-course-prefixed-source-refs",
    )

    assert result.returncode == 1
    assert "STRUCTURAL: MANIFEST_TARGET_OWNER_MISMATCH" in result.stdout
    assert "STRUCTURAL: MISSING_FRONTMATTER_SOURCE_EVIDENCE" in result.stdout
    assert "structural_issues" in result.stdout
