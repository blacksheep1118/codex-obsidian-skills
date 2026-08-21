import check_language_rigor
from check_language_rigor import (
    audit_line,
    classify_claim,
    deduplicate_issues,
    mask_inline_code,
    visible_wikilink_text,
)


def test_unqualified_absolute_claim_is_reported() -> None:
    issues = audit_line("BatchNorm解决梯度消失。", 1, "demo.md")
    assert [issue.term for issue in issues] == ["解决"]
    assert "缓解" in issues[0].suggestion
    assert issues[0].category == "ENGINEERING_PROMISE"


def test_negated_and_conditional_claims_are_allowed() -> None:
    assert audit_line("BatchNorm不能完全解决梯度消失，在该设置下通常有助于稳定训练。", 2, "demo.md") == []


def test_first_claim_requires_citation_but_evidence_claim_can_be_kept() -> None:
    assert audit_line("该方法首次提出统一框架。", 3, "demo.md")
    assert audit_line("论文首次提出统一框架，并在实验中显著提升 PSNR。", 4, "demo.md") == []


def test_technical_complete_term_is_not_a_performance_claim() -> None:
    assert audit_line("完全二叉树的高度为 h。", 5, "demo.md") == []


def test_commonmark_code_span_with_shorter_inner_ticks_is_masked() -> None:
    line = "`` code ` [[x]] 解决保证 ``"
    assert mask_inline_code(line).strip() == ""
    assert audit_line(line, 6, "demo.md") == []


def test_longer_backtick_run_does_not_close_a_shorter_code_span() -> None:
    line = "`` code ``` 解决保证 ``"
    assert mask_inline_code(line).strip() == ""


def test_unconditional_universal_guarantee_is_high_confidence() -> None:
    issues = audit_line("该系统保证所有请求成功。", 7, "demo.md")
    assert [issue.term for issue in issues] == ["保证"]
    assert issues[0].high_confidence is True
    assert issues[0].category == "ENGINEERING_PROMISE"


def test_claim_categories_keep_formal_and_negated_context_distinct() -> None:
    assert classify_claim("保证", "该算法保证所有请求成功。") == "ENGINEERING_PROMISE"
    assert classify_claim("保证", "该措施并不自动保证安全。") == "NEGATED_GUARANTEE"
    assert classify_claim("保证", "该策略通常保证较稳定的训练过程。") == "MANUAL_REVIEW"
    assert classify_claim("保证", "在给定条件下保证最短路正确。") == "CONDITIONAL_GUARANTEE"
    assert classify_claim("必然", "定理证明该结论必然成立。") == "FORMAL_GUARANTEE"
    assert classify_claim("首次提出", "该论文首次提出统一框架。") == "EMPIRICAL_OVERCLAIM"


def test_hedges_are_not_mistaken_for_negation() -> None:
    review = audit_line("该策略通常保证较稳定的训练过程。", 20, "demo.md")
    assert len(review) == 1
    assert review[0].category == "MANUAL_REVIEW"
    assert review[0].high_confidence is False

    universal = audit_line("该方法通常保证所有训练都稳定。", 21, "demo.md")
    assert len(universal) == 1
    assert universal[0].category == "ENGINEERING_PROMISE"
    assert universal[0].high_confidence is True


def test_claim_categories_cover_math_and_reporting_boundaries() -> None:
    assert classify_claim("保证", "满足下界条件时可找到存在的最小解图。") == "CONDITIONAL_GUARANTEE"
    assert classify_claim("保证", "DP 是对相邻数据集输出分布的量化保证。") == "FORMAL_GUARANTEE"
    assert classify_claim("保证", "实施则明确“未提供 DP 保证”。") == "QUESTION_OR_QUOTE"
    assert classify_claim("显著提升", "结果显示该方法显著提升性能。") == "EMPIRICAL_OVERCLAIM"
    assert classify_claim("保证", "该工程保证所有请求成功。") == "ENGINEERING_PROMISE"


def test_table_schema_labels_are_not_engineering_claims() -> None:
    header = "| 类型/算法 | 面试中常用的保证 | 容易说错的边界 |"
    assert classify_claim("保证", header) == "LABEL_OR_SCHEMA"
    assert audit_line(header, 18, "demo.md") == []
    assert audit_line("11. **通用 MIP 解决所有图问题**：专门算法可能快得多。", 19, "demo.md") == []

    claim_after_label = audit_line(
        "- **工程提示**：该系统保证所有请求成功。", 20, "demo.md"
    )
    assert len(claim_after_label) == 1
    assert claim_after_label[0].category == "ENGINEERING_PROMISE"
    assert claim_after_label[0].high_confidence is True


def test_scoped_guarantees_and_rejected_forcing_are_not_overclaims() -> None:
    assert audit_line("原子替换通常只在同一文件系统内有保证。", 20, "demo.md") == []
    assert audit_line("实际要求依 DBMS 而定，由唯一索引保证唯一。", 21, "demo.md") == []
    assert audit_line("组合通常优于强迫一种算法解决全部层次。", 22, "demo.md") == []


def test_definition_and_financial_compound_are_not_absolute_claims() -> None:
    assert audit_line("在数学定义中，数学上必然有 x=x。", 8, "demo.md") == []
    assert audit_line("保证金比例是保证金与融资交易金额之比。", 9, "demo.md") == []
    assert audit_line("质量保证属于项目管理职能。", 10, "demo.md") == []
    assert audit_line("该协议保证消息按序交付。", 11, "demo.md") == []
    assert audit_line("该措施并不自动保证安全。", 12, "demo.md") == []
    assert audit_line("这个方法是否能解决分布漂移？", 13, "demo.md") == []
    assert audit_line("满足下界条件时可找到存在的最小解图。", 14, "demo.md") == []
    assert audit_line("实施则明确“未提供 DP 保证”。", 15, "demo.md") == []


def test_wikilink_alias_audits_only_visible_label() -> None:
    assert visible_wikilink_text("[[隐藏/保证所有请求成功|可见标签]]").strip() == "可见标签"
    assert audit_line("[[隐藏/保证所有请求成功|可见标签]]", 10, "demo.md") == []

    assert audit_line("[[软件工程/普通目标|质量保证]]", 14, "demo.md") == []


def test_bare_wikilink_uses_visible_basename_once() -> None:
    assert audit_line("[[软件工程/质量保证]]", 15, "demo.md") == []


def test_bare_wikilink_keeps_visible_basename_and_heading() -> None:
    line = "[[普通目标#保证所有请求成功]]"
    assert visible_wikilink_text(line).strip() == "普通目标#保证所有请求成功"

    issues = audit_line(line, 16, "demo.md")
    assert [issue.term for issue in issues] == ["保证"]
    assert "普通目标#保证所有请求成功" in issues[0].sentence


def test_embedded_wikilink_is_not_visible_prose() -> None:
    line = "![[普通目标#保证所有请求成功]]"
    assert visible_wikilink_text(line).strip() == ""
    assert audit_line(line, 14, "demo.md") == []


def test_output_deduplicates_same_term_and_sentence() -> None:
    issues = audit_line("该流程保证可复现，也保证可比较。", 17, "demo.md")
    assert len(issues) == 2
    assert len(deduplicate_issues(issues)) == 1


def test_scan_ignores_tilde_and_long_backtick_fences(monkeypatch, tmp_path) -> None:
    note = tmp_path / "demo.md"
    note.write_text(
        "~~~text\n该系统保证所有请求成功。\n~~~\n"
        "````text\n```\n该系统保证所有请求成功。\n````\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_language_rigor, "markdown_files", lambda: [note])
    monkeypatch.setattr(check_language_rigor, "rel", lambda path: path.name)
    monkeypatch.setattr(check_language_rigor, "read_text", lambda path: path.read_text(encoding="utf-8"))
    monkeypatch.setattr(check_language_rigor, "infer_note_type", lambda path: "course_note")

    assert check_language_rigor.scan_notes() == []
