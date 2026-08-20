#!/usr/bin/env python3
"""Classify and quality-check worked examples in all note forms.

``check_examples.py`` owns the source/PPT table contract.  This companion
checker deliberately has a wider lens: it also reports explicit narrative
example sections, inline ``例题：``/``示例：`` blocks, and deliberately marked
code examples.  It does not treat every occurrence of the word ``example`` as
a worked exercise; source-coverage tables, manifests, templates, and generic
prose are excluded so the report remains actionable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from check_examples import generic_prompt
from notes_utils import (
    infer_note_type,
    markdown_files,
    read_text,
    rel,
    split_table_row,
)

TABLE_HEADING = "## PPT/PDF 例题辅助理解"
SKIP_NOTE_TYPES = {
    "agent_rule",
    "audit_record",
    "coverage_audit",
    "global_coverage_audit",
    "source_manifest",
    "source_manifest_history",
    "template",
    "vault_audit",
}
SKIP_NAME_RE = re.compile(r"(^|/)99_|全仓例题索引|source_manifest", re.I)
HEADING_EXAMPLE_RE = re.compile(
    r"(?:例题|例子|示例|算例|案例|练习|题目|Example|Question|Demo|Sample)", re.I
)
INLINE_EXAMPLE_RE = re.compile(
    r"^(?:源资料|课件|PPT/PDF)?\s*(?:例题|例子|示例|算例|案例|练习|Example|Question)\s*[:：]",
    re.I,
)
CODE_MARKER_RE = re.compile(
    r"(?:代码示例|示例代码|源码例子|code\s+example|demo|sample|\bexample\b|示例)",
    re.I,
)
STRONG_PROBLEM_RE = re.compile(
    r"(?:题目|问题|Question|(?<!要)求|计算|证明|给定|已知|输入|输出|请(?:求|计算|证明|判断|说明)|\?)",
    re.I,
)


def mask_inline_code(text: str) -> str:
    """Blank CommonMark code spans using equal-length backtick runs."""

    chars = list(text)
    index = 0
    length = len(text)
    while index < length:
        if text[index] != "`":
            index += 1
            continue
        opening_end = index
        while opening_end < length and text[opening_end] == "`":
            opening_end += 1
        run = text[index:opening_end]
        closing = opening_end
        while closing < length:
            if text[closing] != "`":
                closing += 1
                continue
            closing_end = closing
            while closing_end < length and text[closing_end] == "`":
                closing_end += 1
            if closing_end - closing == len(run):
                break
            closing = closing_end
        if closing >= length:
            index = opening_end
            continue
        end = closing + len(run)
        chars[index:end] = [" "] * (end - index)
        index = end
    return "".join(chars)


@dataclass(frozen=True)
class Example:
    path: Path
    line: int
    kind: str
    title: str
    text: str


def _regular_note(path: Path) -> bool:
    return not SKIP_NAME_RE.search(rel(path)) and infer_note_type(path) not in SKIP_NOTE_TYPES


def _heading_ranges(lines: list[str]) -> list[tuple[int, int, int, str]]:
    """Return ``(start, end, level, title)`` for candidate example sections."""

    headings: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        match = re.match(r"^(#{2,6})\s+(.+?)\s*$", line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2)))

    candidates: list[tuple[int, int, int, str]] = []
    for position, (start, level, title) in enumerate(headings):
        if title == TABLE_HEADING or not HEADING_EXAMPLE_RE.search(title):
            continue
        # A subsection ends at the next heading of the same or higher level.
        end = len(lines)
        for next_start, next_level, _next_title in headings[position + 1 :]:
            if next_level <= level:
                end = next_start
                break
        candidates.append((start, end, level, title))
    # Prefer the outer worked-example section.  A nested ``### 题目`` or
    # ``### 解答`` heading is a structural part of that section, not a second
    # example whose answer is missing.
    ranges = [
        candidate
        for candidate in candidates
        if not any(
            outer[0] < candidate[0]
            and outer[1] >= candidate[1]
            and outer[2] < candidate[2]
            for outer in candidates
        )
    ]
    return ranges


def _iter_table_examples(path: Path, lines: list[str]):
    in_section = False
    for index, line in enumerate(lines):
        if line == TABLE_HEADING:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            in_section = False
        if not in_section or not line.startswith("|") or line.startswith("|---"):
            continue
        cells = split_table_row(line)
        if len(cells) < 3 or cells[0] == "知识点":
            continue
        yield Example(path, index + 1, "table", cells[0], line)


def _iter_narrative_examples(path: Path, lines: list[str]):
    ranges = _heading_ranges(lines)
    for start, end, _level, title in ranges:
        body = "\n".join(lines[start + 1 : end]).strip()
        if not body:
            continue
        # A heading such as “案例背景” is still useful for inventory, but a
        # source-coverage row or a one-line mention is not a worked example.
        if len(re.sub(r"\s+", "", body)) < 25:
            continue
        yield Example(path, start + 1, "narrative", title, f"{title}\n{body}")


def _iter_inline_examples(path: Path, lines: list[str], heading_ranges):
    in_code = False
    covered = {index for start, end, _level, _title in heading_ranges for index in range(start, end)}
    for index, line in enumerate(lines):
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or index in covered or line.startswith("#") or line.startswith("|"):
            continue
        if not INLINE_EXAMPLE_RE.search(line.strip()):
            continue
        text = line.strip()
        # Include the adjacent solution/list/code block.  Many teaching notes
        # put ``例题：`` on one line and the answer after a blank line, so
        # scoring only the label would create a false missing-answer warning.
        tail: list[str] = []
        blank_run = 0
        cursor = index + 1
        while cursor < len(lines) and cursor < index + 32:
            following = lines[cursor]
            if following.startswith("#"):
                break
            if not following.strip():
                blank_run += 1
                if blank_run >= 2:
                    break
                tail.append("")
                cursor += 1
                continue
            blank_run = 0
            tail.append(following)
            # Consume a fenced block as part of the example, including its
            # closing fence and any immediate output line.
            if following.startswith("```"):
                cursor += 1
                while cursor < len(lines) and cursor < index + 32:
                    tail.append(lines[cursor])
                    if lines[cursor].startswith("```"):
                        break
                    cursor += 1
            cursor += 1
        if tail:
            text += "\n" + "\n".join(tail)
        elif len(re.sub(r"\s+", "", INLINE_EXAMPLE_RE.sub("", text))) < 8:
            # A bare label with no adjacent material is not independently
            # scorable; a marked code block or heading will cover its content.
            continue
        yield Example(path, index + 1, "inline", text.split("：", 1)[0].split(":", 1)[0], text)


def _iter_code_examples(path: Path, lines: list[str], heading_ranges):
    in_code = False
    start = 0
    block: list[str] = []
    opening = ""
    for index, line in enumerate(lines):
        if line.startswith("```"):
            if not in_code:
                in_code = True
                start = index
                opening = line
                block = []
                continue
            in_code = False
            preceding = "\n".join(lines[max(0, start - 3) : start])
            first_lines = "\n".join(block[:3])
            marker = bool(CODE_MARKER_RE.search(opening) or CODE_MARKER_RE.search(preceding) or CODE_MARKER_RE.search(first_lines))
            if marker:
                title = next(
                    (line.strip().lstrip("# ") for line in reversed(lines[max(0, start - 3) : start]) if line.strip()),
                    "代码示例",
                )
                text = "\n".join(block)
                if text.strip():
                    yield Example(path, start + 1, "code", title, text)
            continue
        if in_code:
            block.append(line)


def iter_examples():
    """Yield all explicit example candidates with their source line."""

    for path in markdown_files():
        if not _regular_note(path):
            continue
        lines = read_text(path).splitlines()
        ranges = _heading_ranges(lines)
        yield from _iter_table_examples(path, lines)
        yield from _iter_narrative_examples(path, lines)
        yield from _iter_inline_examples(path, lines, ranges)
        yield from _iter_code_examples(path, lines, ranges)


def example_type(text: str, kind: str | None = None) -> str:
    if kind == "code":
        return "代码型"
    if re.search(r"\d|=|\\frac|\\sum|\\begin|矩阵|概率|计算|公式", text):
        return "计算型"
    if any(word in text for word in ["算法", "步骤", "更新", "搜索", "训练", "推理"]):
        return "算法型"
    if any(word in text for word in ["案例", "场景", "系统", "平台", "项目"]):
        return "案例型"
    if any(word in text for word in ["证明", "推导", "为什么", "判定"]):
        return "推导型"
    return "概念型"


def _compact(text: str, kind: str) -> str:
    # Only a fence at the beginning of a line denotes a fenced block.  An
    # inline CommonMark span may itself use a three-backtick run, and treating
    # that run as a fence would expose the span's prose to the quality scan.
    if kind == "code" or re.search(r"(?m)^\s*```", text):
        text = re.sub(r"(?m)^\s*```[^\n]*", "", text)
        return re.sub(r"\s+", "", text)
    compact = mask_inline_code(text)
    compact = re.sub(r"<br\s*/?>", " ", compact)
    return re.sub(r"\s+", "", compact)


def _has_steps(text: str, kind: str) -> bool:
    numbered = len(re.findall(r"(?m)^\s*(?:\d+[.)]|[-*])\s+", text)) >= 2
    cues = any(
        word in text
        for word in [
            "先",
            "再",
            "代入",
            "计算",
            "更新",
            "推导",
            "逐步",
            "首先",
            "然后",
            "通过",
            "构造",
            "比较",
            "判断",
            "解法",
            "步骤",
            "查",
            "取",
            "分解",
            "分别",
            "由",
            "设",
            "令",
            "归一化",
            "合成",
            "引入",
            "处理",
            "缓解",
            "监控",
            "管理",
            "每个",
            "相加",
            "乘",
            "除",
        ]
    )
    code_like = bool(re.search(r"(?m)^\s*(?:def|class|for|while|if|assert|return|print)\b", text))
    if kind == "code":
        return numbered or code_like
    return numbered or cues or code_like


def _has_result(text: str, kind: str) -> bool:
    cues = [
        "答案",
        "结论",
        "因此",
        "所以",
        "得到",
        "最终",
        "说明",
        "意味着",
        "可知",
        "接受",
        "不接受",
        "区别",
        "含义",
        "输出",
        "结果",
        "共",
        "总计",
        "参数量",
        "风险暴露值",
    ]
    if bool(re.search(r"\b(?:assert|print|return|expected|output|result)\b", text, re.I)):
        return True
    if bool(re.search(r"(?:=|≈)\s*(?:\$|`|\\|\d|\{|\(|[A-Za-z])", text)):
        return True
    return any(word in text for word in cues)


def _has_boundary(text: str) -> bool:
    return any(word in text for word in ["易错", "边界", "条件", "陷阱", "注意", "若", "当", "但", "只有", "不能", "不", "仅", "区别"])


def grade(line: str, kind: str = "table") -> str:
    """Grade one table row or an extracted narrative/code candidate."""

    if generic_prompt(line):
        return "D"
    # Table rows keep the established contract: grade the explanation cell,
    # not the topic/source columns.
    text = line.split("解析：", 1)[1] if kind == "table" and "解析：" in line else line
    compact = _compact(text, kind)
    has_steps = _has_steps(text, kind)
    has_result = _has_result(text, kind)
    has_boundary = _has_boundary(text)
    has_computation = bool(re.search(r"(?:\\begin|\\frac|=|\d)\s*", text))
    has_structure = "```" in text or bool(re.search(r"(?:=>|->|\n\s*\|)", text))
    if len(compact) >= 70 and has_steps and has_result and has_boundary:
        return "A"
    if len(compact) >= 45 and ((has_steps and has_result) or (has_computation and has_result)):
        # A long procedural paragraph is not automatically a reproducible
        # example.  B requires either a concrete computation or an explicit
        # condition/boundary; generic step/result boilerplate stays reviewable
        # at C instead of passing the worked-example gate.
        return "B" if has_boundary or has_computation else "C"
    if len(compact) >= 25 and has_structure:
        return "B"
    if kind == "code" and len(compact) >= 50 and (has_steps or has_result):
        return "B" if has_result else "C"
    if len(compact) >= 70 and has_steps and has_result:
        return "B"
    if len(compact) >= 30:
        return "C"
    return "D"


def _requires_solution(example: Example) -> bool:
    """Return whether a candidate is phrased as a question/worked exercise."""

    title = example.title
    if example.kind == "table":
        return True
    if re.search(r"例题|练习|Question|题目|算例", title, re.I):
        if re.search(r"第一个练习|练习：拆|例题思路|复习", title):
            return bool(re.search(r"(?:计算|求解|答案|结论|最终|得到|=)", example.text)) and "思路" not in title
        return True
    if example.kind == "code":
        return _has_steps(example.text, example.kind) and _has_result(example.text, example.kind)
    # “示例/例子/案例” is often explanatory prose rather than an exercise.
    # Require an explicit problem or a numerical/algorithmic result before it
    # enters the strict worked-example gate.
    if re.search(r"示例|例子|案例", title, re.I):
        if "案例" in title and not re.search(r"(?:计算|求解|答案|结论|最终|得到|=|\d)", example.text):
            return False
        return bool(STRONG_PROBLEM_RE.search(example.text) and _has_result(example.text, example.kind))
    return bool(STRONG_PROBLEM_RE.search(example.text))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="fail when a worked candidate remains at grade C or D")
    args = parser.parse_args()

    type_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    grade_counts: Counter[str] = Counter()
    low_grade: list[str] = []
    worked_grade_counts: Counter[str] = Counter()
    non_worked_grade_counts: Counter[str] = Counter()
    total = 0
    required_total = 0
    for example in iter_examples():
        total += 1
        kind_counts[example.kind] += 1
        type_counts[example_type(example.text, example.kind)] += 1
        current_grade = grade(example.text, example.kind)
        grade_counts[current_grade] += 1
        if _requires_solution(example):
            required_total += 1
            worked_grade_counts[current_grade] += 1
            if current_grade in {"C", "D"}:
                low_grade.append(f"{rel(example.path)}:{example.line} | {example.kind} | {example.title} | {current_grade}")
        else:
            non_worked_grade_counts[current_grade] += 1

    payload = {
        "examples_analyzed": total,
        "worked_candidates": required_total,
        "kind_counts": dict(sorted(kind_counts.items())),
        "type_counts": dict(sorted(type_counts.items())),
        "grade_counts": dict(sorted(grade_counts.items())),
        "worked_grade_counts": dict(sorted(worked_grade_counts.items())),
        "non_worked_grade_counts": dict(sorted(non_worked_grade_counts.items())),
        "low_grade_examples": low_grade[:100],
        "low_grade_count": len(low_grade),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"examples_analyzed {total}")
        print(f"worked_candidates {required_total}")
        for key, value in sorted(kind_counts.items()):
            print(f"kind_{key} {value}")
        for key, value in sorted(type_counts.items()):
            print(f"type_{key} {value}")
        for key, value in sorted(grade_counts.items()):
            print(f"grade_{key} {value}")
        for key, value in sorted(worked_grade_counts.items()):
            print(f"worked_grade_{key} {value}")
        for key, value in sorted(non_worked_grade_counts.items()):
            print(f"non_worked_grade_{key} {value}")
        print(f"low_grade_count {len(low_grade)}")
        for item in low_grade[:30]:
            print(f"LOW {item}")
    return 1 if args.strict and low_grade else 0


if __name__ == "__main__":
    sys.exit(main())
