import json
import subprocess
import sys
from pathlib import Path

from algorithm_job_taxonomy import DIRECTIONS as CANONICAL_DIRECTIONS


ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scripts" / "check_algorithm_job_vault.py"
SUBPROCESS_TIMEOUT_SECONDS = 60
KEY_FILES = (
    "00_算法岗学习地图.md",
    "01_岗位地图与学习方法.md",
    "34_官方JD样本与岗位能力矩阵.md",
    "97_算法岗知识体系覆盖矩阵.md",
    "算法岗知识点精简复习版_含公式.md",
    "算法岗知识点详细版_含公式.md",
)
DIRECTIONS = tuple(direction.label for direction in CANONICAL_DIRECTIONS)
ENTRIES = (
    "37_CV_视觉基础模型视频与部署.md",
    "35_NLP_LLM_训练对齐Agent与评测.md",
    "22_推荐系统_召回_排序与深度模型.md",
    "69_搜索算法_Query理解相关性LTR与语义检索.md",
    "38_语音_ASR_TTS与Speech2Speech.md",
    "79_机器人状态估计_SLAM标定融合与定位.md",
    "60_汽车算法_感知融合BEV占用与预测.md",
    "81_具身智能_VLA模仿学习离线RL与Sim2Real.md",
    "40_AI_Infra_CUDA与训练推理优化.md",
    "49_数据结构与算法_复杂度与高频范式.md",
    "108_C++17算法面试_STL与边界.md",
    "115_算法训练_对拍错题复做与模拟面试.md",
    "116_机器学习与深度学习手写题_NumPy_PyTorch与数值稳定.md",
)


def make_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    algorithm = vault / "算法岗学习笔记"
    algorithm.mkdir(parents=True)
    body = "\n".join(f"## {direction}\n路线入口" for direction in DIRECTIONS)
    for filename in KEY_FILES:
        (algorithm / filename).write_text(f"# 导航\n{body}\n", encoding="utf-8")
    for filename in ENTRIES:
        (algorithm / filename).write_text("---\ncourse: 算法岗学习笔记\n---\n# 条目\n", encoding="utf-8")
    return vault


def run_scan(vault: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, str(SCANNER), str(vault), "--json"],
        capture_output=True,
        text=True,
        check=False,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    return result.returncode, json.loads(result.stdout)


def test_valid_nine_direction_fixture_passes(tmp_path):
    code, payload = run_scan(make_vault(tmp_path))
    assert code == 0
    assert payload["ok"] is True
    assert payload["issues"] == []


def test_missing_direction_is_reported(tmp_path):
    vault = make_vault(tmp_path)
    path = vault / "算法岗学习笔记" / KEY_FILES[0]
    path.write_text(path.read_text(encoding="utf-8").replace("## AI Infra\n路线入口\n", ""), encoding="utf-8")
    code, payload = run_scan(vault)
    assert code == 1
    assert any("AI Infra" in issue for issue in payload["issues"])


def test_direction_only_in_code_or_larger_ascii_token_does_not_satisfy_navigation(tmp_path):
    vault = make_vault(tmp_path)
    path = vault / "算法岗学习笔记" / KEY_FILES[0]
    text = path.read_text(encoding="utf-8").replace("## CV\n路线入口\n", "")
    path.write_text(text + "\n```text\nCV\n```\nCVR 是另一个指标。\n", encoding="utf-8")

    code, payload = run_scan(vault)

    assert code == 1
    assert any("missing canonical direction 'CV'" in issue for issue in payload["issues"])


def test_direction_only_in_frontmatter_does_not_satisfy_navigation(tmp_path):
    vault = make_vault(tmp_path)
    path = vault / "算法岗学习笔记" / KEY_FILES[0]
    body = path.read_text(encoding="utf-8").replace("## CV\n路线入口\n", "")
    path.write_text("---\naliases: [CV]\n---\n" + body, encoding="utf-8")

    code, payload = run_scan(vault)

    assert code == 1
    assert any("missing canonical direction 'CV'" in issue for issue in payload["issues"])


def test_extra_route_is_reported_but_natural_topic_prose_is_allowed(tmp_path):
    vault = make_vault(tmp_path)
    map_path = vault / "算法岗学习笔记" / KEY_FILES[0]
    map_path.write_text(map_path.read_text(encoding="utf-8") + "\n## 强化学习算法岗路线\n", encoding="utf-8")
    code, payload = run_scan(vault)
    assert code == 1
    assert any("强化学习算法岗" in issue for issue in payload["issues"])

    natural_vault = make_vault(tmp_path / "natural")
    (natural_vault / "算法岗学习笔记" / "35_NLP_LLM_训练对齐Agent与评测.md").write_text(
        "正文讨论强化学习、GNN、RAG 和多模态模型，但它们不是岗位分类。\n", encoding="utf-8"
    )
    code, payload = run_scan(natural_vault)
    assert code == 0, payload


def test_extra_route_in_topic_file_is_reported(tmp_path):
    vault = make_vault(tmp_path)
    topic = vault / "算法岗学习笔记" / "35_NLP_LLM_训练对齐Agent与评测.md"
    topic.write_text(topic.read_text(encoding="utf-8") + "\n## 强化学习算法岗路线\n", encoding="utf-8")

    code, payload = run_scan(vault)

    assert code == 1
    assert any("强化学习算法岗" in issue and topic.name in issue for issue in payload["issues"])


def test_extra_route_in_plain_prose_and_only_bypass_are_reported(tmp_path):
    vault = make_vault(tmp_path)
    topic = vault / "算法岗学习笔记" / "35_NLP_LLM_训练对齐Agent与评测.md"
    topic.write_text(
        topic.read_text(encoding="utf-8")
        + "\n下一阶段将强化学习算法岗路线作为新的求职入口。\n"
        + "只能新增多模态算法岗路线。\n",
        encoding="utf-8",
    )

    code, payload = run_scan(vault)

    assert code == 1
    assert any("强化学习算法岗" in issue for issue in payload["issues"])
    assert any("多模态算法岗" in issue for issue in payload["issues"])


def test_explicitly_rejected_extra_route_is_allowed(tmp_path):
    vault = make_vault(tmp_path)
    topic = vault / "算法岗学习笔记" / "35_NLP_LLM_训练对齐Agent与评测.md"
    topic.write_text(
        topic.read_text(encoding="utf-8")
        + "\n强化学习算法岗不是独立方向。\n"
        + "不要创建多模态算法岗路线。\n",
        encoding="utf-8",
    )

    code, payload = run_scan(vault)

    assert code == 0, payload


def test_prefixed_rejection_verbs_do_not_create_false_extra_routes(tmp_path):
    vault = make_vault(tmp_path)
    topic = vault / "算法岗学习笔记" / "35_NLP_LLM_训练对齐Agent与评测.md"
    topic.write_text(
        topic.read_text(encoding="utf-8")
        + "\n禁止创建强化学习算法岗路线。\n"
        + "不得新增多模态算法岗路线。\n"
        + "不应创建风控算法岗路线。\n",
        encoding="utf-8",
    )

    code, payload = run_scan(vault)

    assert code == 0, payload


def test_non_route_table_column_and_not_constitute_wording_are_allowed(tmp_path):
    vault = make_vault(tmp_path)
    topic = vault / "算法岗学习笔记" / "35_NLP_LLM_训练对齐Agent与评测.md"
    topic.write_text(
        topic.read_text(encoding="utf-8")
        + "\n| 看到的主题 | 归属方式 | 不能做的事 |\n"
        + "|---|---|---|\n"
        + "| 多模态 | 挂回九方向 | 创建多模态算法岗路线 |\n"
        + "\n本页不构成独立的“遥感算法岗”路线。\n",
        encoding="utf-8",
    )

    code, payload = run_scan(vault)

    assert code == 0, payload


def test_route_inside_tilde_fence_is_not_reported(tmp_path):
    vault = make_vault(tmp_path)
    topic = vault / "算法岗学习笔记" / "35_NLP_LLM_训练对齐Agent与评测.md"
    topic.write_text(
        topic.read_text(encoding="utf-8") + "\n~~~text\n## 强化学习算法岗路线\n~~~\n",
        encoding="utf-8",
    )

    code, payload = run_scan(vault)

    assert code == 0, payload


def test_shorter_backtick_run_does_not_close_longer_fence(tmp_path):
    vault = make_vault(tmp_path)
    topic = vault / "算法岗学习笔记" / "35_NLP_LLM_训练对齐Agent与评测.md"
    topic.write_text(
        topic.read_text(encoding="utf-8")
        + "\n````text\n```\n## 强化学习算法岗路线\n````\n",
        encoding="utf-8",
    )

    code, payload = run_scan(vault)

    assert code == 0, payload


def test_indented_pseudo_fence_does_not_hide_visible_route(tmp_path):
    vault = make_vault(tmp_path)
    topic = vault / "算法岗学习笔记" / "35_NLP_LLM_训练对齐Agent与评测.md"
    topic.write_text(
        topic.read_text(encoding="utf-8")
        + "\n    ```text\n## 强化学习算法岗路线\n    ```\n",
        encoding="utf-8",
    )

    code, payload = run_scan(vault)

    assert code == 1
    assert any("强化学习算法岗" in issue for issue in payload["issues"])


def test_backtick_in_fence_info_does_not_hide_visible_route(tmp_path):
    vault = make_vault(tmp_path)
    topic = vault / "算法岗学习笔记" / "35_NLP_LLM_训练对齐Agent与评测.md"
    topic.write_text(
        topic.read_text(encoding="utf-8")
        + "\n```bad`info\n## 强化学习算法岗路线\n```\n",
        encoding="utf-8",
    )

    code, payload = run_scan(vault)

    assert code == 1
    assert any("强化学习算法岗" in issue for issue in payload["issues"])


def test_frontmatter_issue_reports_physical_line_number(tmp_path):
    vault = make_vault(tmp_path)
    entry = vault / "算法岗学习笔记" / ENTRIES[0]
    entry.write_text("---\njob_track: risk_control\n---\n# 条目\n", encoding="utf-8")

    code, payload = run_scan(vault)

    assert code == 1
    assert any("legacy frontmatter direction at line 2" in issue for issue in payload["issues"])


def test_inline_frontmatter_direction_list_accepts_canonical_ids(tmp_path):
    vault = make_vault(tmp_path)
    entry = vault / "算法岗学习笔记" / ENTRIES[0]
    entry.write_text(
        "---\njob_tracks: [cv, ai_infra]\n---\n# 条目\n",
        encoding="utf-8",
    )

    code, payload = run_scan(vault)

    assert code == 0, payload


def test_inline_frontmatter_unknown_direction_is_reported_once(tmp_path):
    vault = make_vault(tmp_path)
    entry = vault / "算法岗学习笔记" / ENTRIES[0]
    entry.write_text(
        "---\njob_tracks: [cv, mystery_track]\n---\n# 条目\n",
        encoding="utf-8",
    )

    code, payload = run_scan(vault)

    assert code == 1
    matching = [issue for issue in payload["issues"] if "unknown frontmatter direction" in issue]
    assert len(matching) == 1
    assert "line 2" in matching[0]


def test_combined_route_and_old_frontmatter_are_reported(tmp_path):
    vault = make_vault(tmp_path)
    map_path = vault / "算法岗学习笔记" / KEY_FILES[0]
    map_path.write_text(map_path.read_text(encoding="utf-8") + "\n## 搜索与推荐路线\n", encoding="utf-8")
    entry = vault / "算法岗学习笔记" / ENTRIES[0]
    entry.write_text("---\njob_track: risk_control\n---\n# 条目\n", encoding="utf-8")
    code, payload = run_scan(vault)
    assert code == 1
    assert any("搜索与推荐路线" in issue for issue in payload["issues"])
    assert any("frontmatter" in issue for issue in payload["issues"])


def test_extra_matrix_column_is_reported(tmp_path):
    vault = make_vault(tmp_path)
    map_path = vault / "算法岗学习笔记" / KEY_FILES[0]
    map_path.write_text(
        map_path.read_text(encoding="utf-8")
        + "\n| 知识点 | CV | NLP / LLM | 强化学习 |\n",
        encoding="utf-8",
    )
    code, payload = run_scan(vault)
    assert code == 1
    assert any("matrix header" in issue for issue in payload["issues"])


def test_missing_dsa_entry_is_reported(tmp_path):
    vault = make_vault(tmp_path)
    (vault / "算法岗学习笔记" / "49_数据结构与算法_复杂度与高频范式.md").unlink()
    code, payload = run_scan(vault)
    assert code == 1
    assert any("49_数据结构与算法" in issue for issue in payload["issues"])
