#!/usr/bin/env python3
"""Read-only structural scanner for algorithm-job Obsidian vaults."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from algorithm_job_taxonomy import (
    CANONICAL_IDS,
    CANONICAL_LABELS,
    COMBINED_ROUTE_PHRASES,
    FRONTMATTER_DIRECTION_KEYS,
    KEY_NAVIGATION_FILES,
    LEGACY_MATRIX_LABELS,
    LEGACY_ROUTE_PHRASES,
    LEGACY_VALUE_TOKENS,
    all_entry_files,
)

ALGORITHM_DIR_NAME = "算法岗学习笔记"
REQUIRED_FILES = {
    "49_数据结构与算法_复杂度与高频范式.md",
    "108_C++17算法面试_STL与边界.md",
    "115_算法训练_对拍错题复做与模拟面试.md",
    "116_机器学习与深度学习手写题_NumPy_PyTorch与数值稳定.md",
}
OLD_ROUTE_FILE_STEMS = (
    "36_搜索与推荐_",
    "39_机器人与具身智能_",
    "73_应用安全与实时决策_",
    "74_时序回测与研究偏差_",
    "75_时序预测与优化_",
    "95_物流调度与供应链优化_",
    "100_通用机器学习_",
    "102_时序建模_",
    "103_强化学习_",
    "104_因果推断与实验_",
    "106_优化与运筹_",
    "107_多模态技术_",
)
ROUTE_CONTEXT_RE = re.compile(r"岗位|方向|路线|入口|地图|矩阵|分类|主线|track|direction|route", re.I)
HEADING_RE = re.compile(r"^#{1,4}\s+(.+?)\s*$")
FRONTMATTER_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$")
GENERIC_DIRECTION_VALUES = {"p0", "p1", "p2", "foundation", "common", "cross-cutting", "cross_cutting", "topic", "application"}


def _frontmatter(text: str) -> list[str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    try:
        end = lines.index("---", 1)
    except ValueError:
        return []
    return lines[1:end]


def _frontmatter_values(lines: list[str]):
    active_key: str | None = None
    for line in lines:
        if line.startswith("  - "):
            if active_key:
                yield active_key, line[4:].strip().strip('"\'')
            continue
        match = FRONTMATTER_LINE_RE.match(line)
        if not match:
            active_key = None
            continue
        active_key = match.group(1)
        value = match.group(2).strip().strip('"\'[]')
        if value:
            yield active_key, value


def _route_issues(relative: str, line: str) -> list[str]:
    if not ROUTE_CONTEXT_RE.search(line):
        return []
    if line.lstrip().startswith("|") and "创建" in line:
        return []
    if any(marker in line for marker in ("不能", "禁止", "不设置", "不再", "不要", "只能", "归属", "挂靠", "错误信息架构")):
        return []
    return [
        f"{relative}: route boundary contains extra category {phrase!r}"
        for phrase in sorted(LEGACY_ROUTE_PHRASES | COMBINED_ROUTE_PHRASES)
        if phrase in line
    ]


def _matrix_header_issues(relative: str, line: str) -> list[str]:
    if not line.lstrip().startswith("|") or ("知识点" not in line and "岗位方向" not in line):
        return []
    cells = {cell.strip().strip("`*\"'") for cell in line.strip().strip("|").split("|")}
    return [f"{relative}: matrix header contains extra top-level category {label!r}" for label in sorted(LEGACY_MATRIX_LABELS & cells)]


def scan(root: Path) -> dict[str, object]:
    issues: list[str] = []
    algorithm_dir = root / ALGORITHM_DIR_NAME
    if not algorithm_dir.is_dir():
        return {"ok": False, "issues": [f"missing directory: {ALGORITHM_DIR_NAME}"]}
    for filename in REQUIRED_FILES:
        if not (algorithm_dir / filename).is_file():
            issues.append(f"missing required entry: {filename}")
    for filename in all_entry_files():
        if not (algorithm_dir / filename).is_file():
            issues.append(f"missing canonical direction entry: {filename}")
    for path in algorithm_dir.glob("*.md"):
        if any(path.name.startswith(stem) for stem in OLD_ROUTE_FILE_STEMS):
            issues.append(f"obsolete route file remains: {path.name}")
    for filename in KEY_NAVIGATION_FILES:
        path = algorithm_dir / filename
        if not path.is_file():
            issues.append(f"missing key navigation: {filename}")
            continue
        text = path.read_text(encoding="utf-8")
        relative = f"{ALGORITHM_DIR_NAME}/{filename}"
        issues.extend(
            f"{relative}: missing canonical direction {label!r}"
            for label in sorted(CANONICAL_LABELS)
            if label not in text
        )
        for line_number, line in enumerate(text.splitlines(), 1):
            issues.extend(f"{issue} at line {line_number}" for issue in _matrix_header_issues(relative, line))
            if HEADING_RE.match(line) or line.lstrip().startswith(("- ", "* ", "| ")):
                issues.extend(f"{issue} at line {line_number}" for issue in _route_issues(relative, line))
    for path in algorithm_dir.glob("*.md"):
        relative = f"{ALGORITHM_DIR_NAME}/{path.name}"
        lines = _frontmatter(path.read_text(encoding="utf-8"))
        for line_number, line in enumerate(lines, 1):
            match = FRONTMATTER_LINE_RE.match(line)
            key = match.group(1) if match else None
            if key not in FRONTMATTER_DIRECTION_KEYS:
                continue
            value = match.group(2).strip().strip('"\'[]')
            normalized = value.lower().replace(" ", "_").replace("/", "_")
            if normalized in LEGACY_VALUE_TOKENS or any(phrase.lower() in value.lower() for phrase in LEGACY_ROUTE_PHRASES):
                issues.append(f"{relative}: legacy frontmatter direction at line {line_number}")
            elif value and normalized not in CANONICAL_IDS and normalized not in GENERIC_DIRECTION_VALUES:
                issues.append(f"{relative}: unknown frontmatter direction at line {line_number}")
        for key, value in _frontmatter_values(lines):
            normalized = value.lower().replace(" ", "_").replace("/", "_").strip("[]\"'")
            if key in FRONTMATTER_DIRECTION_KEYS and normalized and normalized not in CANONICAL_IDS and normalized not in GENERIC_DIRECTION_VALUES:
                issues.append(f"{relative}: unknown frontmatter direction in list {key!r}")
            if key in {"aliases", "tags"} and any(phrase.lower() in value.lower() for phrase in LEGACY_ROUTE_PHRASES):
                issues.append(f"{relative}: legacy route phrase in frontmatter {key!r}: {value!r}")
    return {
        "ok": not issues,
        "root": str(root),
        "algorithm_files": len(list(algorithm_dir.glob("*.md"))),
        "canonical_directions": sorted(CANONICAL_LABELS),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="vault root to inspect")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = scan(args.root.resolve())
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"algorithm_job_files {payload.get('algorithm_files', 0)}")
        print(f"algorithm_job_directions {len(CANONICAL_LABELS)}")
        print(f"algorithm_job_issues {len(payload['issues'])}")
        for issue in payload["issues"]:
            print(f"ISSUE {issue}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
