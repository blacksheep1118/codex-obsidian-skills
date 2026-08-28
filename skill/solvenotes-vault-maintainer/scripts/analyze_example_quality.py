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
from typing import Iterable

from check_examples import explanation_text, generic_prompt
from notes_utils import (
    infer_note_type,
    markdown_files,
    read_text,
    rel,
    split_table_row,
)

TABLE_TITLE = "PPT/PDF 例题辅助理解"
TABLE_HEADING = f"## {TABLE_TITLE}"
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
    r"(?:题目|问题|Question|(?<![需要])求|计算(?!机)|证明|给定|已知|输入|输出|请(?:求|计算|证明|判断|说明)|\?)",
    re.I,
)
EXPLICIT_EXERCISE_RE = re.compile(
    r"(?:题目|问题|Question|(?<![需要])求|计算(?!机)|证明|给定|已知|"
    r"请(?:求|计算|证明|判断|说明)|\?)",
    re.I,
)
NEGATED_CONCRETE_TASK_RE = re.compile(
    r"(?:没有|不含|不包含|缺少|不涉及|未涉及|并未涉及)\s*(?:给出|提供)?\s*"
    r"(?:任何|具体的?|明确的?|实际的?|可核验的?|可复算的?)?\s*"
    r"(?:题目|例题|练习|案例|示例|条件|失败情形|依据|计算|推导|证明)"
    r"|(?:没有|不含|不包含|缺少|不涉及|未涉及|并未涉及)\s*(?:给出|提供)?\s*"
    r"(?:可核验的?|可复算的?|具体的?|明确的?)\s*(?:输入|数值|数据)",
    re.S,
)
CONCRETE_TASK_RE = re.compile(
    r"(?:题目|给定|已知|输入|要求|假设|条件|如果|若|当且仅当|当.{1,40}时|"
    r"计算|推导|证明|判断|比较|区分|检查|观察|核对|验证|评估|代入|求解|输出|边界|易错|反例|构造|"
    r"模拟|扫描|标记|状态|分支|接受|拒绝|归纳|反设|等价|定理|语言|"
    r"自动机|字符串|只需|=|≈|\\frac|\\sum|\\begin|\\to|\$|ε|→|\d)",
    re.S,
)
BOUNDARY_RE = re.compile(
    r"(?:易错|边界|条件|陷阱|注意|如果|若|(?:当|时)?且仅当|仅当|当.{1,40}时|"
    r"只有|除非|否则|不能|不可|不会|不等于|不成立|不意味着|不表示|不代表|"
    r"不足以|并非|不是|区别|才(?:算|能|会|可|进入|构成|支持|成立|说明|表明|属于|接受|拒绝|得到)|"
    r"但是|然而|仍(?:需|要)|还要|需.{0,16}(?:核对|验证|判断))",
    re.S,
)
FORMAL_ARGUMENT_RE = re.compile(
    r"(?:证明|推导|归纳|反设|构造|不变量|等价|(?:当|时)?且仅当|矛盾|"
    r"充分|必要|保持.{0,20}不变)",
    re.S,
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
        if title == TABLE_TITLE or not HEADING_EXAMPLE_RE.search(title):
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
            "扫描",
            "标记",
            "移动",
            "写入",
            "归约",
            "递归",
            "猜测",
            "计数",
            "保存",
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
        "拒绝",
        "区别",
        "含义",
        "输出",
        "结果",
        "共",
        "总计",
        "参数量",
        "风险暴露值",
        "源资料给出",
    ]
    if bool(re.search(r"\b(?:assert|print|return|expected|output|result)\b", text, re.I)):
        return True
    if bool(re.search(r"(?:=|≈)\s*(?:\$|`|\\|\d|\{|\(|[A-Za-z])", text)):
        return True
    return any(word in text for word in cues)


def _has_boundary(text: str) -> bool:
    return bool(BOUNDARY_RE.search(text))


def _has_concrete_task(text: str) -> bool:
    """Require an actual condition, datum, or formal relation, not process prose."""

    formal_data = bool(re.search(r"(?:=|≈|\\frac|\\sum|\\begin|\\to|\$|ε|→|\d)", text))
    if NEGATED_CONCRETE_TASK_RE.search(text) and not formal_data:
        return False
    return bool(CONCRETE_TASK_RE.search(text))


def grade(line: str, kind: str = "table") -> str:
    """Grade one table row or an extracted narrative/code candidate."""

    if generic_prompt(line):
        return "D"
    # Table rows keep the established contract: grade the explanation cell,
    # not the topic/source columns.
    text = explanation_text(line) if kind == "table" else line
    compact = _compact(text, kind)
    has_steps = _has_steps(text, kind)
    has_result = _has_result(text, kind)
    has_boundary = _has_boundary(text)
    has_concrete_task = _has_concrete_task(text)
    has_formal_argument = bool(FORMAL_ARGUMENT_RE.search(text))
    has_computation = bool(re.search(r"(?:\\begin|\\frac|=|\d)\s*", text))
    has_structure = "```" in text or bool(re.search(r"(?:=>|->|\n\s*\|)", text))
    if len(compact) >= 70 and has_steps and has_result and has_boundary and has_concrete_task:
        return "A"
    if (
        len(compact) >= 45
        and has_concrete_task
        and ((has_steps and has_result) or (has_computation and has_result))
    ):
        # A long procedural paragraph is not automatically a reproducible
        # example.  B requires either a concrete computation or an explicit
        # condition/boundary; generic step/result boilerplate stays reviewable
        # at C instead of passing the worked-example gate.
        return "B" if has_boundary or has_computation or has_formal_argument else "C"
    if len(compact) >= 25 and has_structure and (kind != "table" or has_concrete_task):
        return "B"
    if kind == "code" and len(compact) >= 50 and (has_steps or has_result):
        return "B" if has_result else "C"
    if len(compact) >= 70 and has_steps and has_result:
        return "C"
    if len(compact) >= 30:
        return "C"
    return "D"


def _requires_solution(example: Example) -> bool:
    """Return whether a candidate is phrased as a question/worked exercise."""

    title = example.title
    if example.kind == "table":
        return True
    if re.search(r"不是.{0,30}(?:例子|示例|案例)", title):
        return False
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
        return bool(EXPLICIT_EXERCISE_RE.search(example.text) and _has_result(example.text, example.kind))
    return bool(STRONG_PROBLEM_RE.search(example.text))


def semantic_category(example: Example) -> str:
    """Classify the candidate by its teaching role instead of an opaque grade."""

    if re.search(r"(?:索引|入口|参见|详见)", example.title):
        return "index_reference"
    if re.search(r"(?:自检维度|评分标准|评分要点)", example.title):
        return "not_an_example"
    needs_solution = _requires_solution(example)
    current_grade = grade(example.text, example.kind)
    has_result = _has_result(example.text, example.kind)
    if needs_solution:
        if not has_result:
            return "missing_answer"
        if current_grade in {"C", "D"}:
            return "insufficient_conditions"
        if re.search(r"(?:自编|原创|生成)", example.text):
            return "original_exercise"
        if re.search(r"(?:课件|PPT|源资料|来源)", example.text, re.I):
            return "source_example"
        return "worked_example"
    if example.kind == "code":
        return "code_demonstration"
    if has_result and not STRONG_PROBLEM_RE.search(example.text):
        return "answer_only"
    if re.search(r"示例|例子|案例|Demo|Sample", example.title, re.I):
        return "concept_illustration"
    return "not_an_example"


def build_report(examples: Iterable[Example]) -> dict[str, object]:
    """Build the semantic report used by both JSON and text output."""

    type_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    category_paths: dict[str, list[str]] = {}
    failures: list[str] = []
    total = 0
    required_total = 0
    for example in examples:
        total += 1
        kind_counts[example.kind] += 1
        type_counts[example_type(example.text, example.kind)] += 1
        category = semantic_category(example)
        category_counts[category] += 1
        category_paths.setdefault(category, []).append(
            f"{rel(example.path)}:{example.line} | {example.kind} | {example.title}"
        )
        if category in {"worked_example", "source_example", "original_exercise"}:
            required_total += 1
        elif category in {"missing_answer", "insufficient_conditions"}:
            required_total += 1
            failures.append(
                f"{rel(example.path)}:{example.line} | {example.kind} | {example.title} | {category}"
            )

    worked_example_count = sum(
        category_counts[name]
        for name in ("worked_example", "source_example", "original_exercise")
    )
    return {
        "examples_analyzed": total,
        "worked_candidates": required_total,
        "worked_example_count": worked_example_count,
        "non_worked_candidates": total - required_total,
        "kind_counts": dict(sorted(kind_counts.items())),
        "type_counts": dict(sorted(type_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "category_paths": {key: value for key, value in sorted(category_paths.items())},
        "gate_failures": failures,
        "gate_failure_count": len(failures),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail when a worked candidate is missing an answer or has insufficient conditions",
    )
    args = parser.parse_args()

    payload = build_report(iter_examples())
    failures = payload["gate_failures"]
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"examples_analyzed {payload['examples_analyzed']}")
        print(f"worked_candidates {payload['worked_candidates']}")
        print(f"worked_example_count {payload['worked_example_count']}")
        print(f"non_worked_candidates {payload['non_worked_candidates']}")
        for key, value in payload["kind_counts"].items():
            print(f"kind_{key} {value}")
        for key, value in payload["type_counts"].items():
            print(f"type_{key} {value}")
        for key, value in payload["category_counts"].items():
            print(f"category_{key} {value}")
        print(f"gate_failure_count {payload['gate_failure_count']}")
        for item in failures[:30]:
            print(f"FAIL {item}")
    return 1 if args.strict and failures else 0


if __name__ == "__main__":
    sys.exit(main())
