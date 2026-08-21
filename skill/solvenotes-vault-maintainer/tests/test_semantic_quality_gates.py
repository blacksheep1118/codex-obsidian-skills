from pathlib import Path

import analyze_example_quality
from analyze_example_quality import (
    Example,
    _compact,
    build_report,
    grade,
    mask_inline_code,
    semantic_category,
)
from check_examples import generic_prompt
from check_paper_notes import paper_contract_gaps


def test_explicit_paper_contract_passes() -> None:
    sections = []
    for heading in ["问题缺口", "核心方法", "实验结论", "失败边界", "可复现要点"]:
        sections.append(f"## {heading}\n\n" + (f"{heading}的证据、机制、条件和结论。" * 12))

    assert paper_contract_gaps("# 完整论文笔记\n\n" + "\n\n".join(sections)) == []


def test_short_paper_contract_reports_missing_sections() -> None:
    assert "问题缺口" in paper_contract_gaps("# 方法名\n\n## 核心方法\n\n只有一句方法简介。\n")


def test_repeated_keyword_pile_does_not_satisfy_paper_contract() -> None:
    repeated = "问题 方法 实验 结果 局限 复现 " * 520
    note = "# 伪论文\n\n" + "\n\n".join(
        f"## {heading}\n\n{repeated}" for heading in ["问题缺口", "核心方法", "实验结论", "失败边界", "可复现要点"]
    )
    assert paper_contract_gaps(note) == ["问题缺口", "核心方法", "实验结论", "失败边界", "可复现要点"]


def test_generic_example_prompt_is_grade_d() -> None:
    line = (
        "| A* | 完整练习：写出题目已知条件、算法步骤，并说明输入改变后的结论变化。"
        "<br>解析：先把 A* 翻译成变量、参数、目标函数和约束条件，再解释结果。 | 生成 |"
    )

    assert generic_prompt(line) is not None
    assert grade(line) == "D"


def test_worked_example_reaches_grade_a() -> None:
    line = (
        "| 轮转调度 | 已知三个进程到达时间均为0，服务时间为3、2、1，时间片为1。"
        "<br>解析：首先按到达顺序建立队列；逐步更新后完成时刻为6、5、3。"
        "因此周转时间分别为6、5、3，最终平均值为14/3。易错点是进程未结束时必须重新入队。 | 生成 |"
    )

    assert grade(line) == "A"


def test_generic_steps_and_result_do_not_reach_grade_b() -> None:
    line = "解析：首先读取输入数据，然后执行算法步骤，接着更新状态，最后输出结果，因此得到最终结果并说明计算完成。"
    assert grade(line) == "C"


def test_example_report_categories_explain_quality_without_letter_grades(monkeypatch) -> None:
    source = Example(
        Path("course.md"),
        10,
        "table",
        "轮转调度",
        "| 轮转调度 | 已知三个进程到达时间均为0，服务时间为3、2、1，课件例题要求计算周转时间。"
        "解析：先按到达顺序建立队列，再逐个时间片更新剩余时间，最终完成时刻为6、5、3，"
        "平均周转时间为14/3；边界是未结束进程必须重新入队。 | 来源 |",
    )
    missing = Example(Path("course.md"), 20, "narrative", "练习", "题目：给定三个进程，请计算周转时间。")

    assert semantic_category(source) == "source_example"
    assert semantic_category(missing) == "missing_answer"

    monkeypatch.setattr(analyze_example_quality, "rel", lambda path: path.as_posix())
    report = build_report([source, missing])
    assert report["worked_candidates"] == 2
    assert report["worked_example_count"] == 1
    assert report["gate_failure_count"] == 1


def test_commonmark_code_span_with_shorter_inner_ticks_is_ignored() -> None:
    text = "`` code ` [[x]] 解决保证 ``"
    assert mask_inline_code(text).strip() == ""
    assert _compact(text, "table") == ""


def test_longer_backtick_run_does_not_close_shorter_example_span() -> None:
    text = "`` code ``` 解决保证 ``"
    assert mask_inline_code(text).strip() == ""
    assert _compact(text, "table") == ""
