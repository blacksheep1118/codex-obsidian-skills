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
