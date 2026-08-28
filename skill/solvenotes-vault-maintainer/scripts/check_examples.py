#!/usr/bin/env python3
"""Check PPT/PDF worked examples and reject visible audit residue in notes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from notes_utils import (
    infer_note_type,
    is_table_separator,
    markdown_files,
    read_text,
    rel,
    split_table_row,
)

EXAMPLE_HEADING = "## PPT/PDF 例题辅助理解"
SUPPLEMENT_HEADING = "## PPT/PDF 页级补充索引"
START = "<!-- source-coverage:start -->"
END = "<!-- source-coverage:end -->"
SKIP_NOTE_TYPES = {
    "agent_rule",
    "source_manifest",
    "template",
    "vault_audit",
}
GENERATED_SOURCE_MARKERS = (
    "自拟教学例：源课件未提供可独立还原的对应例题",
    "生成：PPT/PDF 未提供独立可抽取例题",
)
NATURAL_GENERATED_SOURCE_PATTERNS = (
    re.compile(
        r"(?:自拟|自编|原创).{0,120}(?:源课件|课件|源资料|论文|讲义).{0,120}"
        r"(?:未提供|没有提供|未给出|没有给出|未包含|没有包含).{0,80}"
        r"(?:例题|练习|题目|案例|示例|数值|数据|条件|答案|解法|对应)",
        re.S,
    ),
    re.compile(
        r"(?:源课件|课件|源资料|论文|讲义).{0,120}"
        r"(?:未提供|没有提供|未给出|没有给出|未包含|没有包含).{0,80}"
        r"(?:例题|练习|题目|案例|示例|数值|数据|条件|答案|解法|对应).{0,120}"
        r"(?:自拟|自编|原创)",
        re.S,
    ),
    re.compile(
        r"(?:自拟|自编|原创).{0,80}(?:并非|不是|不属于|非)\s*"
        r"(?:源课件|课件|源资料|论文|讲义).{0,40}(?:原题|例题|练习|题目|案例|示例)",
        re.S,
    ),
)
NEGATED_SELF_WRITTEN_RE = re.compile(
    r"(?:不是|并非|不属于|不算|不能算|称不上|谈不上|非)\s*"
    r"(?:(?:真正(?:意义上)?|所谓|严格意义上|课件中|课程中|源课件中|源资料中|论文中)的?\s*)?"
    r"(?:一(?:个|道|项|份))?\s*"
    r"(?:自拟|自编|原创)(?:教学)?(?:题|例|例题|练习|案例|示例)?"
)
TRACEABLE_SOURCE_FILE_RE = re.compile(
    r"\.(?:pdf|pptx?)(?:\b|(?=[`#?]))",
    re.I,
)

GENERIC_PROMPT_PATTERNS = (
    re.compile(r"完整练习：写出题目已知条件"),
    re.compile(r"请说明它对应的知识点，并分析输入或条件改变后的结论变化"),
    re.compile(r"识别变量.{0,20}写步骤.{0,20}解释结果.{0,20}改输入重算"),
)
QUOTED_TOPIC_RE = re.compile(r"“[^”]{1,100}”")
NEGATED_SUBSTANCE_RE = re.compile(
    r"(?:没有|不含|不包含|缺少|不涉及|未涉及|并未涉及)\s*(?:给出|提供)?\s*"
    r"(?:任何|具体的?|明确的?|实际的?|可核验的?|可复算的?)?\s*"
    r"(?:步骤|结论|依据|题目|例题|练习|案例|示例|条件|失败情形|计算|推导|证明)"
    r"|(?:没有|不含|不包含|缺少|不涉及|未涉及|并未涉及)\s*(?:给出|提供)?\s*"
    r"(?:可核验的?|可复算的?|具体的?|明确的?)\s*(?:输入|数值|数据)",
    re.S,
)
DETAIL_SIGNAL_RE = re.compile(
    r"(?:题目|给定|已知|输入|要求|假设|条件|如果|若|当且仅当|当.{1,40}时|"
    r"计算|推导|证明|判断|比较|代入|首先|然后|步骤|结论|因此|所以|可知|"
    r"意味着|输出|边界|易错|反例|构造|模拟|扫描|标记|状态|分支|接受|"
    r"拒绝|归纳|反设|等价|说明|解释|只需|保持|读入|=|≈|\\frac|\\sum|"
    r"\\begin|\\to|\$|ε|→|\d)",
    re.S,
)
EXAMPLE_COLUMN_HEADER_RE = re.compile(
    r"(?:例题(?:[/／]辅助题)?|辅助题)(?:[与及](?:详细)?(?:解析|解答))?"
)
SOURCE_COLUMN_HEADER_RE = re.compile(r"(?:资料)?来源(?:说明|文件)?|源(?:资料|文件)")


@dataclass(frozen=True)
class ExampleTableColumns:
    topic: int
    explanation: int
    source: int


def example_table_columns(cells: list[str]) -> ExampleTableColumns | None:
    """Resolve the example-table contract from its header, independent of order."""

    headers = [re.sub(r"\s+", "", cell).strip("`*_ ") for cell in cells]
    topic = [index for index, header in enumerate(headers) if header in {"知识点", "主题", "考点"}]
    explanation = [
        index
        for index, header in enumerate(headers)
        if EXAMPLE_COLUMN_HEADER_RE.fullmatch(header)
    ]
    source = [
        index
        for index, header in enumerate(headers)
        if SOURCE_COLUMN_HEADER_RE.fullmatch(header)
    ]
    if len(topic) != 1 or len(explanation) != 1 or len(source) != 1:
        return None
    resolved = ExampleTableColumns(topic[0], explanation[0], source[0])
    if len({resolved.topic, resolved.explanation, resolved.source}) != 3:
        return None
    return resolved


def default_example_table_columns(cells: list[str]) -> ExampleTableColumns | None:
    if len(cells) < 3:
        return None
    return ExampleTableColumns(0, len(cells) - 2, len(cells) - 1)


def canonical_example_row(cells: list[str], columns: ExampleTableColumns) -> str:
    return "| " + " | ".join(
        (cells[columns.topic], cells[columns.explanation], cells[columns.source])
    ) + " |"


def resolved_example_table_rows(
    indexed_lines: Iterable[tuple[int, str]],
) -> Iterable[tuple[int, str, list[str], ExampleTableColumns]]:
    """Yield data rows after resolving the first table row as the header once."""

    table_columns: ExampleTableColumns | None = None
    header_checked = False
    for line_number, line in indexed_lines:
        cells = split_table_row(line)
        if not cells or is_table_separator(line):
            continue
        if not header_checked:
            header_checked = True
            table_columns = example_table_columns(cells)
            if table_columns is not None:
                continue
        active_columns = table_columns or default_example_table_columns(cells)
        if active_columns is None or max(
            active_columns.topic,
            active_columns.explanation,
            active_columns.source,
        ) >= len(cells):
            continue
        yield line_number, line, cells, active_columns


def section_lines(lines: list[str], heading: str) -> list[str]:
    try:
        start = lines.index(heading)
    except ValueError:
        return []
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## ") and lines[i] != heading:
            end = i
            break
    return lines[start + 1 : end]


def explanation_text(line: str, columns: ExampleTableColumns | None = None) -> str:
    cells = split_table_row(line)
    active_columns = columns or default_example_table_columns(cells)
    if active_columns is not None and active_columns.explanation < len(cells):
        explanation = cells[active_columns.explanation]
        return explanation.split("解析：", 1)[1] if "解析：" in explanation else explanation
    if "解析：" in line:
        return line.split("解析：", 1)[1]
    return ""


def compact_explanation(line: str, columns: ExampleTableColumns | None = None) -> str:
    explanation = explanation_text(line, columns)
    explanation = re.sub(r"`[^`]*`", "", explanation)
    explanation = re.sub(r"<br\s*/?>", " ", explanation)
    return re.sub(r"\s+", "", explanation)


def explanation_is_detailed(line: str, columns: ExampleTableColumns | None = None) -> bool:
    explanation = explanation_text(line, columns)
    if len(compact_explanation(line, columns)) < 30 or NEGATED_SUBSTANCE_RE.search(explanation):
        return False
    return bool(DETAIL_SIGNAL_RE.search(explanation))


def generic_prompt(line: str) -> str | None:
    for pattern in GENERIC_PROMPT_PATTERNS:
        match = pattern.search(line)
        if match:
            return match.group(0)
    return None


def normalized_explanation(line: str, columns: ExampleTableColumns | None = None) -> str:
    """Normalize a solution so copied domain templates group together."""

    explanation = explanation_text(line, columns)
    explanation = QUOTED_TOPIC_RE.sub("“{主题}”", explanation)
    explanation = re.sub(r"`[^`]*`", "", explanation)
    explanation = re.sub(r"<br\s*/?>", " ", explanation)
    return re.sub(r"\s+", "", explanation)


def regular_note(path) -> bool:
    return infer_note_type(path) not in SKIP_NOTE_TYPES


def has_generated_source_marker(text: str) -> bool:
    candidate = NEGATED_SELF_WRITTEN_RE.sub("", text)
    if any(marker in candidate for marker in GENERATED_SOURCE_MARKERS):
        return True
    return any(pattern.search(candidate) for pattern in NATURAL_GENERATED_SOURCE_PATTERNS)


def example_source_kind(line: str, columns: ExampleTableColumns | None = None) -> str:
    """Classify one example row without guessing that an unlabeled row is sourced."""

    cells = split_table_row(line)
    active_columns = columns or default_example_table_columns(cells)
    source_cell = (
        cells[active_columns.source]
        if active_columns is not None and active_columns.source < len(cells)
        else ""
    )
    if has_generated_source_marker(source_cell):
        return "generated"
    if "生成辅助题" in line:
        return "generated_unmarked"
    if TRACEABLE_SOURCE_FILE_RE.search(source_cell):
        return "source"
    return "unclassified"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    example_rows = 0
    supplement_rows = 0
    issues: list[str] = []
    source_examples = 0
    generated_examples = 0
    source_coverage_note_blocks = 0
    explanation_locations: dict[str, list[str]] = defaultdict(list)

    for path in markdown_files():
        lines = read_text(path).splitlines()
        if regular_note(path) and any(line in {SUPPLEMENT_HEADING, START, END} for line in lines):
            source_coverage_note_blocks += 1
            issues.append(
                f"{rel(path)}: visible PPT/PDF page-level audit block must be removed from learner-facing note body; "
                "retain necessary extraction limits in source_manifest.md"
            )

        indexed_lines = enumerate(section_lines(lines, EXAMPLE_HEADING), start=1)
        for _line_number, line, cells, active_columns in resolved_example_table_rows(
            indexed_lines
        ):
            example_rows += 1
            if not explanation_is_detailed(line, active_columns):
                issues.append(f"{rel(path)}: example row lacks a detailed teaching explanation")
            prompt = generic_prompt(line)
            if prompt:
                issues.append(f"{rel(path)}: example row contains generic prompt: {prompt}")
            normalized = normalized_explanation(line, active_columns)
            if len(normalized) >= 80:
                explanation_locations[normalized].append(
                    f"{rel(path)} | {cells[active_columns.topic]}"
                )
            source_kind = example_source_kind(line, active_columns)
            if source_kind in {"generated", "generated_unmarked"}:
                generated_examples += 1
            elif source_kind == "source":
                source_examples += 1
            else:
                issues.append(
                    f"{rel(path)}: example row source is unclassified; use a traceable source file "
                    "or an explicit self-written-example rationale"
                )
            if source_kind == "generated_unmarked":
                issues.append(f"{rel(path)}: generated example missing standard source marker")

    for locations in explanation_locations.values():
        if len(locations) < 3:
            continue
        samples = "; ".join(locations[:3])
        issues.append(f"generic explanation reused across {len(locations)} example rows: {samples}")

    payload = {
        "example_rows": example_rows,
        "source_examples": source_examples,
        "generated_examples": generated_examples,
        "supplement_rows": supplement_rows,
        "source_coverage_note_blocks": source_coverage_note_blocks,
        "example_issues": len(issues),
        "issues": issues[:80],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"example_rows {example_rows}")
        print(f"supplement_rows {supplement_rows}")
        print(f"example_issues {len(issues)}")
        for issue in issues[:80]:
            print(f"ISSUE {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
