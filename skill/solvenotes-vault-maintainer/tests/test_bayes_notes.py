import os
from pathlib import Path

ROOT = Path(os.environ["SOLVENOTES_VAULT_ROOT"])


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_bayes_decision_note_states_map_conditions_and_boundary_roots() -> None:
    text = _read("机器学习/10_贝叶斯决策理论.md")

    assert "Maximum A Posteriori" in text
    assert "Maximum posterior probability" not in text
    assert "可能为 0、1、2 个" in text
    assert "更多交点" in text
    assert "0–1 损失" in text
    assert "离散变量" in text and "连续变量" in text
    assert "\\sum_{\\mathbf{x}" in text and "\\int_{\\mathcal X}" in text


def test_rejection_threshold_documents_inclusive_equality() -> None:
    text = _read("机器学习26/03_第三章_贝叶斯分类器与风险决策.md")

    assert "\\le\\theta" in text
    assert "达到阈值也拒绝" in text
    assert "$\\theta=1$ 时所有样本都会被拒绝" in text
