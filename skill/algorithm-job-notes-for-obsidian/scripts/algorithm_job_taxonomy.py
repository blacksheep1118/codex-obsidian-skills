"""Canonical algorithm-job taxonomy for the vault scanner."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Direction:
    id: str
    label: str
    entry_files: tuple[str, ...]


DIRECTIONS = (
    Direction("cv", "CV", ("37_CV_视觉基础模型视频与部署.md",)),
    Direction("nlp_llm", "NLP / LLM", ("35_NLP_LLM_训练对齐Agent与评测.md",)),
    Direction("recommendation", "推荐", ("22_推荐系统_召回_排序与深度模型.md",)),
    Direction("search", "搜索", ("69_搜索算法_Query理解相关性LTR与语义检索.md",)),
    Direction("speech", "语音", ("38_语音_ASR_TTS与Speech2Speech.md",)),
    Direction("robotics", "机器人", ("79_机器人状态估计_SLAM标定融合与定位.md",)),
    Direction("automotive", "汽车算法", ("60_汽车算法_感知融合BEV占用与预测.md",)),
    Direction("embodied_ai", "具身智能", ("81_具身智能_VLA模仿学习离线RL与Sim2Real.md",)),
    Direction("ai_infra", "AI Infra", ("40_AI_Infra_CUDA与训练推理优化.md",)),
)

CANONICAL_IDS = frozenset(direction.id for direction in DIRECTIONS)
CANONICAL_LABELS = frozenset(direction.label for direction in DIRECTIONS)
LEGACY_ROUTE_PHRASES = frozenset(
    {
        "多模态算法岗",
        "强化学习算法岗",
        "图学习算法岗",
        "时序算法岗",
        "广告算法岗",
        "风控算法岗",
        "风险控制算法岗",
        "数据科学岗",
        "量化算法岗",
        "医疗AI算法岗",
        "遥感算法岗",
        "供应链算法岗",
        "RAG算法岗",
        "Agent算法岗",
        "AIGC算法岗",
    }
)
LEGACY_VALUE_TOKENS = frozenset(
    {
        "multimodal",
        "reinforcement_learning",
        "rl",
        "gnn",
        "graph_learning",
        "time_series",
        "advertising",
        "ads",
        "risk_control",
        "data_science",
        "quant",
        "finance",
        "healthcare_ai",
        "remote_sensing",
        "supply_chain",
        "rag",
        "agent",
        "aigc",
        "generative_model",
        "mlops",
    }
)
LEGACY_MATRIX_LABELS = frozenset(
    {
        "多模态",
        "强化学习",
        "图学习",
        "GNN",
        "时序",
        "广告",
        "风控",
        "数据科学",
        "量化",
        "医疗 AI",
        "遥感",
        "供应链",
        "RAG",
        "Agent",
        "AIGC",
        "生成模型",
        "Diffusion",
        "MLOps",
        "自动驾驶",
        "智能驾驶",
    }
)
COMBINED_ROUTE_PHRASES = frozenset({"搜索与推荐路线", "搜索与推荐方向", "机器人与具身智能路线", "机器人与具身方向"})
KEY_NAVIGATION_FILES = (
    "00_算法岗学习地图.md",
    "01_岗位地图与学习方法.md",
    "34_官方JD样本与岗位能力矩阵.md",
    "97_算法岗知识体系覆盖矩阵.md",
    "算法岗知识点精简复习版_含公式.md",
    "算法岗知识点详细版_含公式.md",
)
FRONTMATTER_DIRECTION_KEYS = frozenset(
    {"track", "tracks", "job_track", "job_tracks", "direction", "directions"}
)


def all_entry_files() -> set[str]:
    return {entry for direction in DIRECTIONS for entry in direction.entry_files}
