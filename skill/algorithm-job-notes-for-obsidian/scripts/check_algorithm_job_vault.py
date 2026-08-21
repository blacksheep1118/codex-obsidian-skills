#!/usr/bin/env python3
"""Read-only structural scanner for algorithm-job Obsidian vaults."""

from __future__ import annotations

import argparse
import csv
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
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
FRONTMATTER_LINE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$")
FRONTMATTER_LIST_ITEM_RE = re.compile(r"^\s*-\s+(.+?)\s*$")
GENERIC_DIRECTION_VALUES = {"p0", "p1", "p2", "foundation", "common", "cross-cutting", "cross_cutting", "topic", "application"}
DIRECTION_PATTERNS = {
    label: re.compile(r"(?<![A-Za-z0-9_])CV(?![A-Za-z0-9_])")
    if label == "CV"
    else re.compile(r"NLP\s*/\s*LLM", re.I)
    if label == "NLP / LLM"
    else re.compile(re.escape(label))
    for label in CANONICAL_LABELS
}


def _frontmatter(text: str) -> list[str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    try:
        end = lines.index("---", 1)
    except ValueError:
        return []
    return lines[1:end]


def _inline_values(raw: str) -> list[str]:
    """Parse a scalar or a simple YAML-style inline list without PyYAML."""

    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
        if not value.strip():
            return []
        return [item.strip().strip('"\'') for item in next(csv.reader([value], skipinitialspace=True))]
    return [value.strip('"\'')] if value else []


def _frontmatter_values(lines: list[str]):
    active_key: str | None = None
    for line_number, line in enumerate(lines, 2):
        item_match = FRONTMATTER_LIST_ITEM_RE.match(line)
        if item_match:
            if active_key:
                for value in _inline_values(item_match.group(1)):
                    yield active_key, value, line_number
            continue
        match = FRONTMATTER_LINE_RE.match(line)
        if not match:
            active_key = None
            continue
        active_key = match.group(1)
        for value in _inline_values(match.group(2)):
            yield active_key, value, line_number


def _normalized_direction(value: str) -> str:
    return re.sub(r"[\s/.-]+", "_", value.strip().lower()).strip("_")


def _text_without_fenced_code(text: str) -> str:
    """Remove code fences and comments before checking human-facing routes."""

    kept: list[str] = []
    fence_char = ""
    fence_length = 0
    lines = text.splitlines()
    frontmatter_end = -1
    if lines and lines[0].strip() == "---":
        try:
            frontmatter_end = lines.index("---", 1)
        except ValueError:
            frontmatter_end = -1
    for line_number, line in enumerate(lines):
        if frontmatter_end >= 0 and line_number <= frontmatter_end:
            kept.append("")
            continue
        match = FENCE_RE.match(line)
        if fence_char:
            kept.append("")
            if (
                match
                and match.group(1)[0] == fence_char
                and len(match.group(1)) >= fence_length
                and not match.group(2).strip()
            ):
                fence_char = ""
                fence_length = 0
            continue
        if match:
            marker = match.group(1)
            info = match.group(2)
            if marker[0] == "`" and "`" in info:
                kept.append(line)
                continue
            fence_char = marker[0]
            fence_length = len(marker)
            kept.append("")
            continue
        kept.append(line)
    return HTML_COMMENT_RE.sub("", "\n".join(kept))


def _route_issues(relative: str, line: str) -> list[str]:
    if not ROUTE_CONTEXT_RE.search(line):
        return []

    def explicitly_rejected(start: int, end: int) -> bool:
        before = line[max(0, start - 32) : start]
        after = line[end : end + 40]
        return bool(
            re.search(
                r"(?:禁止(?:创建|新增|保留)?|不得(?:创建|新增|保留|作为)?|"
                r"不应(?:创建|新增|保留|作为)?|不能(?:创建|新增|保留)?|"
                r"不要(?:创建|新增|保留)?|不再|不设置|不新增|不创建|"
                r"不构成|不是|并非|不作为|取消|删除|移除|清理)"
                r"\s*(?:把|将)?\s*(?:独立的)?\s*[“\"']?\s*$",
                before,
            )
            or re.match(
                r"^\s*(?:[|，,:：;；-]\s*)*(?:路线|方向|入口)?\s*"
                r"(?:不是|并非|不作为|不得作为|不再作为|不应作为|不再保留|"
                r"不创建|不新增|已删除|应删除|归属|挂靠|只能作为|仅作为)",
                after,
            )
        )

    issues: list[str] = []
    for phrase in sorted(LEGACY_ROUTE_PHRASES | COMBINED_ROUTE_PHRASES):
        for match in re.finditer(re.escape(phrase), line):
            if not explicitly_rejected(match.start(), match.end()):
                issues.append(
                    f"{relative}: route boundary contains extra category {phrase!r}"
                )
                break
    return issues


def _table_cells(line: str) -> list[str] | None:
    if not line.lstrip().startswith("|"):
        return None
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


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
        visible_text = _text_without_fenced_code(text)
        relative = f"{ALGORITHM_DIR_NAME}/{filename}"
        issues.extend(
            f"{relative}: missing canonical direction {label!r}"
            for label in sorted(CANONICAL_LABELS)
            if not DIRECTION_PATTERNS[label].search(visible_text)
        )
    for path in algorithm_dir.glob("*.md"):
        relative = f"{ALGORITHM_DIR_NAME}/{path.name}"
        text = path.read_text(encoding="utf-8")
        lines = _frontmatter(text)
        for key, value, line_number in _frontmatter_values(lines):
            normalized = _normalized_direction(value)
            if key in FRONTMATTER_DIRECTION_KEYS:
                if normalized in LEGACY_VALUE_TOKENS or any(
                    phrase.lower() in value.lower() for phrase in LEGACY_ROUTE_PHRASES
                ):
                    issues.append(
                        f"{relative}: legacy frontmatter direction at line {line_number}"
                    )
                elif (
                    normalized
                    and normalized not in CANONICAL_IDS
                    and normalized not in GENERIC_DIRECTION_VALUES
                ):
                    issues.append(
                        f"{relative}: unknown frontmatter direction at line {line_number}"
                    )
            if key in {"aliases", "tags"} and any(phrase.lower() in value.lower() for phrase in LEGACY_ROUTE_PHRASES):
                issues.append(f"{relative}: legacy route phrase in frontmatter {key!r}: {value!r}")
        visible_text = _text_without_fenced_code(text)
        rejected_table_columns: set[int] = set()
        for line_number, line in enumerate(visible_text.splitlines(), 1):
            issues.extend(f"{issue} at line {line_number}" for issue in _matrix_header_issues(relative, line))
            cells = _table_cells(line)
            if cells is None:
                rejected_table_columns.clear()
                route_fragments = [line]
            elif _separator_row(cells):
                route_fragments = []
            elif any(re.search(r"不能做|禁止|不得", cell) for cell in cells):
                rejected_table_columns = {
                    index
                    for index, cell in enumerate(cells)
                    if re.search(r"不能做|禁止|不得", cell)
                }
                route_fragments = [
                    cell
                    for index, cell in enumerate(cells)
                    if index not in rejected_table_columns
                ]
            elif rejected_table_columns:
                route_fragments = [
                    cell
                    for index, cell in enumerate(cells)
                    if index not in rejected_table_columns
                ]
            else:
                route_fragments = [line]
            for fragment in route_fragments:
                issues.extend(
                    f"{issue} at line {line_number}"
                    for issue in _route_issues(relative, fragment)
                )
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
