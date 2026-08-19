import pytest
from check_all_notes import content_policy_issues


@pytest.mark.parametrize(
    "residue",
    [
        "UNVERIFIED",
        "## 9. 2025 Lecture 15 页级补充",
        "页级证据：p.1 是标题页。",
        "2025 年正式页级来源是 lecture_15.pdf。",
        "2025 Lecture 11 的页级主线是大规模训练。",
        "代表页级例子见第 7 页。",
        "代表页级公式见第 8 页。",
        "覆盖审查留痕：原关键词弱命中。",
    ],
)
def test_ordinary_notes_reject_precise_audit_residue(residue: str) -> None:
    text = f"# Study note\n\n{residue}\n"

    assert any("ordinary-note audit residue" in issue for issue in content_policy_issues("course/note.md", text))


@pytest.mark.parametrize(
    "relative",
    [
        "course/source_manifest.md",
        "agent/rule.md",
        "模板/course_note.md",
        "scripts/README.md",
        "tests/fixture.md",
    ],
)
def test_audit_residue_exemptions_are_path_exact(relative: str) -> None:
    text = "# Formal or supporting file\n\nUNVERIFIED\n\n覆盖审查留痕：原关键词弱命中。\n"

    assert content_policy_issues(relative, text) == []


def test_legacy_coverage_page_is_rejected_even_without_residue() -> None:
    assert content_policy_issues("course/99_内容覆盖审查.md", "# Legacy page\n") == [
        "1: forbidden legacy audit artifact"
    ]


@pytest.mark.parametrize(
    "sentence",
    [
        "lecture_10.pdf p.7 定义视频张量，p.21–44 介绍 3D CNN。第 7 页图示给出计算流程。",
        "在网页文档分类中，页级证据与文档级标签联合建模。",
        "仅靠文本抽取无法识别表格结构。",
        "页级证据来自第 7 页图示。",
        "该模型把页级主线编码为文档向量的一部分。",
        "版面分析同时学习代表页级特征与段落级特征。",
    ],
)
def test_natural_page_and_document_language_is_allowed_in_ordinary_notes(sentence: str) -> None:
    text = f"# Study note\n\n{sentence}\n"

    assert content_policy_issues("cs231n/video.md", text) == []


def test_removed_audit_block_would_still_be_rejected_if_reintroduced() -> None:
    text = (
        "# Distributed training\n\n"
        "## 2025 Lecture 11 页级补充\n\n"
        "2025 Lecture 11 的页级主线是大规模训练。\n"
        "页级证据：p.35–49 介绍数据并行与梯度平均。\n"
        "若只靠文本抽取无法核对图中箭头，细节仍标为 UNVERIFIED。\n"
        "覆盖审查留痕：原关键词弱命中。\n"
    )

    issues = content_policy_issues("cs231n/distributed-training.md", text)

    assert len(issues) >= 4
    assert all("ordinary-note audit residue" in issue for issue in issues)


def test_precise_fixed_pseudo_question_is_rejected_even_in_legacy_coverage_report() -> None:
    text = "# Coverage\n\n## 自检题\n\n1. 主题 解决的核心问题是什么？它和本课程前后章节的哪个概念最容易混淆？\n"

    issues = content_policy_issues("course/99_内容覆盖审查.md", text)

    assert any("fixed pseudo-question" in issue for issue in issues)


def test_legitimate_self_check_question_is_preserved() -> None:
    text = "# Coverage\n\n## 自检题\n\n1. 平台经济的核心机制是什么？请引用课程案例说明。\n"

    assert content_policy_issues("course/note.md", text) == []


def test_frontmatter_and_fenced_examples_do_not_trigger_content_policy() -> None:
    text = (
        "---\n"
        "aliases: [UNVERIFIED]\n"
        "---\n\n"
        "# Note\n\n"
        "```text\n"
        "## 9. 页级补充\n"
        "主题 解决的核心问题是什么？它和本课程前后章节的哪个概念最容易混淆？\n"
        "```\n\n"
        "Natural prose.\n"
    )

    assert content_policy_issues("course/note.md", text) == []
