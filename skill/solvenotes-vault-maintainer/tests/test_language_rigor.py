from check_language_rigor import (
    audit_line,
    deduplicate_issues,
    mask_inline_code,
    visible_wikilink_text,
)


def test_unqualified_absolute_claim_is_reported() -> None:
    issues = audit_line("BatchNorm解决梯度消失。", 1, "demo.md")
    assert [issue.term for issue in issues] == ["解决"]
    assert "缓解" in issues[0].suggestion


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


def test_definition_and_financial_compound_are_not_absolute_claims() -> None:
    assert audit_line("在数学定义中，数学上必然有 x=x。", 8, "demo.md") == []
    assert audit_line("保证金比例是保证金与融资交易金额之比。", 9, "demo.md") == []
    assert audit_line("质量保证属于项目管理职能。", 10, "demo.md") == []
    assert audit_line("该协议保证消息按序交付。", 11, "demo.md") == []
    assert audit_line("该措施并不自动保证安全。", 12, "demo.md") == []
    assert audit_line("这个方法是否能解决分布漂移？", 13, "demo.md") == []


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
