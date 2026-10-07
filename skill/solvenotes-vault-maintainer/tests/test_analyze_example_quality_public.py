from __future__ import annotations

import importlib
from pathlib import Path

import pytest

CASES = [
    (
        "numeric_derivation",
        "例题：匀速路程",
        "已知一辆小车以每分钟 6 米匀速前进 4 分钟，求路程。先用 s=vt 把速度和时间代入，"
        "得到 s=6×4=24 米；因此在速度保持不变的前提下，路程为 24 米。若速度变化，就按各时间段分别计算。",
        {"worked_example"},
        "A",
    ),
    (
        "symbolic_derivation",
        "例题：记录上界",
        r"给定 $k\le35$ 条待审记录，要求按顺序逐条检查并输出保留项。先处理当前记录，再把通过者加入集合；"
        "每条记录至多访问一次，所以检查次数不超过 35 次。若规则改变，需重新确认上界。",
        {"worked_example"},
        "A",
    ),
    (
        "asymptotic_derivation",
        "例题：扫描复杂度",
        "给定长度为 n 的列表，要求返回最大元素。先记录第一个元素，再逐项扫描并更新记录；"
        "每个元素只访问一次，因此比较次数和复杂度均为 O(n)，最后输出最大元素。",
        {"worked_example"},
        "B",
    ),
    (
        "short_missing_answer",
        "例题：两段用时",
        "已知两段用时分别为 3 和 5，求合计用时。",
        {"missing_answer", "insufficient_conditions"},
        None,
    ),
    (
        "explicit_placeholder",
        "例题：通用流程",
        "先整理输入，再执行计算，最后输出结果；但这里没有提供具体输入数据或可复算数值，不能给出本题答案。",
        {"insufficient_conditions"},
        "C",
    ),
    (
        "relation_with_explicit_gap",
        "例题：范围判断",
        r"已知 $p\le35$，要求判断是否合规。这里不提供判定过程，读者需自行完成。",
        {"missing_answer", "insufficient_conditions"},
        None,
    ),
    (
        "relation_condition_only",
        "例题：范围判断",
        r"已知 $p\le35$，要求判断是否合规。先列条件，再检查输入；若输入改变，重新检查范围。",
        {"missing_answer", "insufficient_conditions"},
        None,
    ),
    (
        "generic_asymptotic_flow",
        "例题：通用扫描",
        "给定一个待处理问题，先分析输入，再初始化状态，然后扫描数据并输出结果；复杂度记作 O(n)，具体规则由读者补充。",
        {"missing_answer", "insufficient_conditions"},
        None,
    ),
    (
        "generic_counted_flow",
        "例题：可复用流程",
        "给定一个待处理问题，先分析输入，再更新状态；每个步骤最多执行一次，复杂度为 O(n)，最后输出结果。",
        {"missing_answer", "insufficient_conditions"},
        None,
    ),
    (
        "connective_without_conclusion",
        "例题：稳定性判断",
        "要求判断设备是否稳定。先检查运行过程；若输入改变，比较两条路径，从而安排后续验证。",
        {"missing_answer", "insufficient_conditions"},
        None,
    ),
    (
        "proof_goal_without_proof",
        "例题：证明算法停机",
        "要求证明算法必然停机。先分析状态，再检查边界；题面只提出证明目标，读者需自行完成论证。",
        {"missing_answer", "insufficient_conditions"},
        None,
    ),
    (
        "fault_condition_without_solution",
        "例题：故障判断",
        "设备发生故障后停止运行，要求判断是否需要更换部件。先记录现象并等待检查；题面没有给出判定过程。",
        {"missing_answer", "insufficient_conditions"},
        None,
    ),
]


@pytest.fixture
def checker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    (tmp_path / "AGENT.md").write_text("# synthetic test vault\n", encoding="utf-8")
    monkeypatch.setenv("SOLVENOTES_VAULT_ROOT", str(tmp_path))
    module = importlib.import_module("analyze_example_quality")
    return importlib.reload(module)


@pytest.mark.parametrize(
    "case_id,title,text,accepted_categories,expected_grade",
    CASES,
    ids=[case[0] for case in CASES],
)
def test_synthetic_example_contract(
    checker,
    tmp_path: Path,
    case_id: str,
    title: str,
    text: str,
    accepted_categories: set[str],
    expected_grade: str | None,
) -> None:
    fixture = tmp_path / f"{case_id}.md"
    fixture.write_text(f"# {title}\n\n{text}\n", encoding="utf-8")
    example = checker.Example(fixture, 1, "narrative", title, f"{title}\n{text}")

    category = checker.semantic_category(example)
    assert category in accepted_categories
    if expected_grade is not None:
        assert checker.grade(text, "narrative") == expected_grade


def test_relation_requires_conclusion_context(checker) -> None:
    assert checker._has_result(r"$p\le35$", "narrative") is False
    assert checker._has_result(r"由前式可知 $p\Rightarrow q$", "narrative") is True
    assert checker._has_result(r"要求推导 $S\Rightarrow T$", "narrative") is False
    assert checker._has_result(r"$\left(p\right)$", "narrative") is False


def test_concrete_counted_asymptotic_example_is_kept(checker) -> None:
    text = (
        "给定一个列表，要求扫描每个元素并更新最大值；每个元素只访问一次，"
        "因此比较次数为 O(n)，最后输出最大值。"
    )
    assert checker.grade(text, "narrative") == "B"


def test_qualitative_case_does_not_require_formulaic_answer_word(checker, tmp_path):
    text = (
        "| 服务平台 | 店铺把供货商和买家连接起来，配送接口让两边交换订单。"
        "商家增加可以拓宽选择，买家增加又可能吸引商家；但只上线自己的商品目录，"
        "没有第三方参与时，更适合作为自营数字渠道分析。网络反馈与普通软件功能需要分别判断。"
        " | 源资料案例：`课程/platform.pdf` p.4 |"
    )
    example = checker.Example(tmp_path / "case.md", 1, "table", "服务平台", text)
    assert checker.semantic_category(example) == "concept_illustration"


@pytest.mark.parametrize("text", [
    "| 用时 | 给定两段用时 3 分钟和 5 分钟，请计算总用时。 | 源资料案例：`课程/time.pdf` p.2 |",
    "| 论证 | 要求证明关系传递性。先查看条件，再检查边界，读者需自行完成论证。 | 源资料思考题：`课程/proof.pdf` p.3 |",
    "| 占位 | 这段描述只介绍一般流程，没有具体题目和依据。先读取输入，再处理记录，最后输出结果；条件变化时重复流程。 | 源资料案例：`课程/case.pdf` p.1 |",
])
def test_case_label_cannot_hide_missing_worked_solution(checker, tmp_path, text):
    example = checker.Example(tmp_path / "gap.md", 1, "table", "练习", text)
    assert checker.semantic_category(example) in {"missing_answer", "insufficient_conditions"}


def test_representation_and_multiple_choice_are_explicit_results(checker, tmp_path):
    graph = "给定动物类和物种类，建立上位关系。可表示为：\n```text\n猫 --AKO--> 哺乳动物\n```\n若结点是个体，使用 ISA 关系，不能与类包含关系混用。"
    choice = "已知文法和输入串，按最右推导的逆序逐步归约；正确选项为 **C**：\n```text\nid ⇒ F ⇒ T ⇒ E\n```\n每次只归约一个句柄，不能跳过中间非终结符。"
    for title, text in [("例题：关系表示", graph), ("练习：归约", choice)]:
        example = checker.Example(tmp_path / "worked.md", 1, "narrative", title, text)
        assert checker.semantic_category(example) == "worked_example"
    assert not checker._has_result("如何表示关系？可表示为：待补。", "narrative")
    assert not checker._has_result("请确定正确选项。", "narrative")


def test_rubric_and_taxonomy_are_not_unanswered_exercises(checker, tmp_path):
    rubric = "10 分练习自检\n| 分值 | 要点 |\n|---|---|\n| 2 | 检查样本 |\n| 2 | 量化不确定性 |"
    taxonomy = "三类建模练习\n1. 概率：掉落和期望。\n2. 曲线：等级与累计经验。\n3. 经济：资源产销与库存。"
    for text in [rubric, taxonomy]:
        example = checker.Example(tmp_path / "guide.md", 1, "narrative", text.split("\n")[0], text)
        assert checker.semantic_category(example) == "not_an_example"
    actual = checker.Example(tmp_path / "exercise.md", 1, "narrative", "三类练习", "三类练习\n给定用时 3 和 5，请计算总用时。")
    assert checker.semantic_category(actual) == "missing_answer"


def test_computing_resource_is_a_concept_not_calculation_request(checker, tmp_path):
    text = "课件示例：\n```text\nWorkerNode\n```\n节点可以是设备或软件执行环境，用于承载部署制品；计算资源描述其角色，不能据节点标签推断处理性能。"
    example = checker.Example(tmp_path / "uml.md", 1, "inline", "课件示例", text)
    assert checker.semantic_category(example) == "concept_illustration"


def test_negative_evidence_limit_is_not_a_proof_request(checker, tmp_path):
    text = (
        "| 证据解释 | 商店上线推荐工具以后销量增加，前后差值仍不足以证明推荐工具带来增量。"
        "需要确认同一商品、人群和观察窗口，并比较同期对照组；季节需求、促销和渠道变化"
        "都可能影响销售。仅凭一组聚合记录不能推出因果效果，缺少对照时应保留这些竞争解释。"
        " | 自拟教学例；背景见 `课程/evidence.pdf` p.5 |"
    )
    example = checker.Example(tmp_path / "evidence.md", 1, "table", "证据解释", text)
    assert checker.semantic_category(example) == "concept_illustration"


@pytest.mark.parametrize("task_instruction", [
    "要求判断关系传递性。",
    "比较两算法的运行开销。",
    "按 RR 算法逐步列出执行序列及周转时间。",
    "给定关系，请构造反例。",
])
def test_qualitative_role_cannot_exempt_explicit_unanswered_tasks(checker, tmp_path, task_instruction):
    text = (
        "| 课堂任务 | " + task_instruction +
        "先观察对象，再检查适用条件。若状态改变，应重新核对操作顺序与约束，"
        "记录各个观察点并保留原始材料。这里只列待检查项，读者需自行完成分析，"
        "后续还需要补充具体对象的处理过程。 | 源资料案例：`课程/tasks.pdf` p.7 |"
    )
    example = checker.Example(tmp_path / "task.md", 1, "table", "课堂任务", text)
    assert checker.semantic_category(example) in {"missing_answer", "insufficient_conditions"}


def test_topic_inventory_does_not_exempt_action_instructions(checker, tmp_path):
    text = "三类建模练习\n1. 构造：请构造反例。\n2. 算法：按 RR 算法逐步列出序列。\n3. 判断：要求判断是否满足约束。"
    example = checker.Example(tmp_path / "tasks.md", 1, "narrative", "三类建模练习", text)
    assert checker.semantic_category(example) in {"missing_answer", "insufficient_conditions"}


@pytest.mark.parametrize("task_instruction", [
    "计算每个进程的等待时间。",
    "给定三个进程，分别在 0、1、2 到达，服务时间为 5、2、1，采用 RR 求每个进程等待时间。",
    "请结合题意分析这两种策略。",
    "请说明各状态的含义。",
])
def test_common_request_variants_still_require_solution(checker, tmp_path, task_instruction):
    text = (
        "| 条件任务 | " + task_instruction +
        "先读取材料，再核对操作条件。若状态发生变化，应重新整理约束并保存观察记录。"
        "本段只安排准备工作，读者需自行完成后续分析，还需要逐项检查对象及相关背景。"
        " | 源资料案例：`课程/tasks.pdf` p.8 |"
    )
    example = checker.Example(tmp_path / "variant.md", 1, "table", "条件任务", text)
    assert checker.semantic_category(example) in {"missing_answer", "insufficient_conditions"}


def test_numbered_item_label_can_contain_an_actual_task(checker, tmp_path):
    text = "三类建模练习\n1. 构造反例：关系 R 包含 a、b、c。\n2. 比较两算法：算法 A 与 B 分别处理同一输入。\n3. 判断是否成立：条件随状态改变。"
    example = checker.Example(tmp_path / "numbered.md", 1, "narrative", "三类建模练习", text)
    assert checker.semantic_category(example) in {"missing_answer", "insufficient_conditions"}


def test_request_and_source_column_do_not_supply_the_answer(checker, tmp_path):
    assert not checker._has_result("请说明各状态的含义。", "narrative")
    assert checker._has_result("请计算合计用时，得到 3+5=8 分钟。", "narrative")
    text = "| 用时 | 给定两段用时 3 和 5，请计算合计用时。 | 来源：`课程/time.pdf` p.2，答案参考本章 |"
    example = checker.Example(tmp_path / "source-answer.md", 1, "table", "用时", text)
    assert checker.semantic_category(example) == "missing_answer"
