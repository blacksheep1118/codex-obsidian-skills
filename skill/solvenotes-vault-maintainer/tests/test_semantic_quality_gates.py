from pathlib import Path

import analyze_example_quality
from analyze_example_quality import (
    TABLE_HEADING,
    Example,
    _compact,
    _heading_ranges,
    _iter_narrative_examples,
    _iter_table_examples,
    build_report,
    grade,
    mask_inline_code,
    semantic_category,
)
from check_examples import (
    example_source_kind,
    example_table_columns,
    explanation_is_detailed,
    explanation_text,
    generic_prompt,
    has_generated_source_marker,
)
from check_paper_notes import paper_contract_gaps
from notes_utils import split_table_row


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


def test_generated_example_marker_accepts_natural_and_legacy_wording() -> None:
    assert has_generated_source_marker("自拟教学例：源课件未提供可独立还原的对应例题")
    assert has_generated_source_marker(
        "自拟教学例：课件只给出背景，没有给出这组数值。"
    )
    assert has_generated_source_marker(
        "自拟教学例：课件只给出背景，没有给出重复 ID 案例。"
    )
    assert has_generated_source_marker("生成：PPT/PDF 未提供独立可抽取例题")
    assert not has_generated_source_marker("这是一个例题")
    assert not has_generated_source_marker("这是自拟教学例，但没有说明来源边界")
    assert not has_generated_source_marker("这是自拟题，沿用课件背景，但答案不是唯一")
    assert not has_generated_source_marker("这是自拟题，没有采用课件中的第二种解法")
    assert not has_generated_source_marker("本题不是自拟题；课件没有给出答案。")
    assert not has_generated_source_marker("本题不是真正的自拟题；课件没有给出答案。")
    assert not has_generated_source_marker("本题不算自拟题；课件没有给出对应答案。")


def test_table_parser_keeps_escaped_pipe_inside_explanation() -> None:
    line = (
        r"| 逻辑析取 | 题目：判断析取式。<br>解析：判断 $p\|q$ 是否成立，再逐项检查真值并给出结论。 "
        r"| `课程/逻辑.pptx` |"
    )

    assert split_table_row(line) == [
        "逻辑析取",
        r"题目：判断析取式。<br>解析：判断 $p\|q$ 是否成立，再逐项检查真值并给出结论。",
        "`课程/逻辑.pptx`",
    ]
    assert explanation_text(line).startswith(r"判断 $p\|q$")


def test_table_parser_accepts_optional_outer_pipes() -> None:
    expected = ["知识点", "例题与解析", "来源"]

    assert split_table_row("| 知识点 | 例题与解析 | 来源") == expected
    assert split_table_row("知识点 | 例题与解析 | 来源 |") == expected
    assert split_table_row("知识点 | 例题与解析 | 来源") == expected
    assert split_table_row(r"知识点 | 判断 $p\|q$ | 来源") == [
        "知识点",
        r"判断 $p\|q$",
        "来源",
    ]


def test_reordered_example_columns_are_resolved_from_header() -> None:
    header = "来源 | 知识点 | 例题与解析"
    row = (
        "`课程/第七讲.ppt` | 图连通性 | 已知有限无向图，从首个顶点开始扫描边并标记相邻顶点；"
        "一轮无新增时停止。因此全部顶点均被标记，当且仅当图连通；易错点是遗漏孤立顶点。"
    )
    columns = example_table_columns(split_table_row(header))

    assert columns is not None
    assert explanation_text(row, columns).startswith("已知有限无向图")
    assert example_source_kind(row, columns) == "source"

    examples = list(
        _iter_table_examples(
            Path("course.md"),
            [TABLE_HEADING, "", header, "---|---|---", row],
        )
    )
    assert len(examples) == 1
    assert examples[0].title == "图连通性"
    assert example_source_kind(examples[0].text) == "source"
    assert grade(examples[0].text) in {"A", "B"}


def test_header_like_data_row_does_not_replace_resolved_columns() -> None:
    lines = [
        TABLE_HEADING,
        "",
        "来源 | 知识点 | 例题与解析 | 备注",
        "---|---|---|---",
        "`课程/第七讲.ppt` | 知识点 | 例题与解析 | 来源",
    ]

    examples = list(_iter_table_examples(Path("course.md"), lines))

    assert len(examples) == 1
    assert examples[0].title == "知识点"
    assert explanation_text(examples[0].text) == "例题与解析"
    assert example_source_kind(examples[0].text) == "source"


def test_example_source_identity_fails_closed() -> None:
    assert (
        example_source_kind(
            "| 图连通性 | 完整解答。 | `课程/第七讲.ppt` |"
        )
        == "source"
    )
    assert (
        example_source_kind(
            "| 数据质量 | 完整解答。 | 自拟教学例：课件没有给出对应案例。 |"
        )
        == "generated"
    )
    assert example_source_kind("| 图连通性 | 完整解答。 | 生成 |") == "unclassified"


def test_table_example_section_is_not_counted_as_narrative() -> None:
    lines = [
        TABLE_HEADING,
        "",
        "| 知识点 | 例题/辅助题与详细解析 | 来源 |",
        "|---|---|---|",
        "| 图连通性 | 扫描边并标记顶点，最终给出判定。 | `课程/第七讲.ppt` |",
    ]

    assert _heading_ranges(lines) == []
    assert len(list(_iter_table_examples(Path("course.md"), lines))) == 1
    assert list(_iter_narrative_examples(Path("course.md"), lines)) == []


def test_worked_example_reaches_grade_a() -> None:
    line = (
        "| 轮转调度 | 已知三个进程到达时间均为0，服务时间为3、2、1，时间片为1。"
        "<br>解析：首先按到达顺序建立队列；逐步更新后完成时刻为6、5、3。"
        "因此周转时间分别为6、5、3，最终平均值为14/3。易错点是进程未结束时必须重新入队。 | 生成 |"
    )

    assert grade(line) == "A"


def test_natural_table_explanation_does_not_require_a_fixed_label() -> None:
    line = (
        "| 图连通性 | 从首个顶点开始，反复扫描边并标记相邻顶点，直到一轮没有新增标记。"
        "因此，全部顶点均被标记，当且仅当图连通；有限顶点保证过程停机。 | `课程/第七讲.ppt` |"
    )

    assert explanation_text(line).startswith("从首个顶点开始")
    assert explanation_is_detailed(line)
    assert grade(line) == "B"


def test_short_natural_table_explanation_still_fails() -> None:
    line = "| 图连通性 | 扫描边并标记顶点。 | `课程/第七讲.ppt` |"

    assert explanation_text(line) == "扫描边并标记顶点。"
    assert not explanation_is_detailed(line)
    assert grade(line) == "D"


def test_long_placeholder_without_substance_still_fails_detail_gate() -> None:
    line = (
        "| 占位说明 | 这是一段长度足够的说明，但没有步骤、结论或具体依据，"
        "也不包含可复算的题目与条件，只用于占据表格位置。 | `课程/第一讲.pptx` |"
    )

    assert not explanation_is_detailed(line)
    assert grade(line) in {"C", "D"}


def test_generic_process_that_denies_a_concrete_task_cannot_reach_grade_b() -> None:
    line = (
        "解析：首先扫描记录并标记状态，然后移动指针、写入结果，最后输出处理结论。"
        "这段描述只介绍一般流程，不包含具体题目或条件，也没有可核验的输入数值。"
    )

    assert grade(line) in {"C", "D"}


def test_process_that_says_it_does_not_cover_concrete_details_still_fails() -> None:
    line = (
        "| 通用流程 | 解析：先读取输入并执行处理，再输出结果。这段说明不涉及具体数据、"
        "计算步骤、边界条件或失败情形，只概括所有任务都能套用的一般流程。 "
        "| `课程/流程.pptx` |"
    )

    assert not explanation_is_detailed(line)
    assert grade(line) in {"C", "D"}


def test_generic_flow_that_admits_it_has_no_actual_example_still_fails() -> None:
    line = (
        "| 占位说明 | 这只是通用流程，没有实际例题。首先检查输入状态，然后更新分支并输出结果；"
        "如果条件变化则重新检查，否则保留当前结论。最后记录结果，说明流程结束。 "
        "| `课程/第一讲.pptx` |"
    )

    assert not explanation_is_detailed(line)
    assert grade(line) in {"C", "D"}


def test_boundary_detection_does_not_match_cjk_substrings() -> None:
    line = (
        "解析：人才系统先扫描记录，再标记状态并输出结果。这个一般流程反复执行，"
        "最终得到处理结果，但没有给出可核验的输入数据。"
    )

    assert grade(line) in {"C", "D"}


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
