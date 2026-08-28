#!/usr/bin/env python3
"""Check PPT/PDF worked examples and reject visible audit residue in notes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict

from notes_utils import infer_note_type, markdown_files, read_text, rel, split_table_row

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


def explanation_text(line: str) -> str:
    cells = split_table_row(line)
    if len(cells) >= 3:
        explanation = cells[-2]
        return explanation.split("解析：", 1)[1] if "解析：" in explanation else explanation
    if "解析：" in line:
        return line.split("解析：", 1)[1]
    return ""


def compact_explanation(line: str) -> str:
    explanation = explanation_text(line)
    explanation = re.sub(r"`[^`]*`", "", explanation)
    explanation = re.sub(r"<br\s*/?>", " ", explanation)
    return re.sub(r"\s+", "", explanation)


def explanation_is_detailed(line: str) -> bool:
    explanation = explanation_text(line)
    if len(compact_explanation(line)) < 30 or NEGATED_SUBSTANCE_RE.search(explanation):
        return False
    return bool(DETAIL_SIGNAL_RE.search(explanation))


def generic_prompt(line: str) -> str | None:
    for pattern in GENERIC_PROMPT_PATTERNS:
        match = pattern.search(line)
        if match:
            return match.group(0)
    return None


def normalized_explanation(line: str) -> str:
    """Normalize a solution so copied domain templates group together."""

    explanation = explanation_text(line)
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


def example_source_kind(line: str) -> str:
    """Classify one example row without guessing that an unlabeled row is sourced."""

    cells = split_table_row(line)
    source_cell = cells[-1] if len(cells) >= 3 else ""
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

        for line in section_lines(lines, EXAMPLE_HEADING):
            if not line.startswith("|") or line.startswith("|---"):
                continue
            cells = split_table_row(line)
            if len(cells) < 3 or cells[0] == "知识点":
                continue
            example_rows += 1
            if not explanation_is_detailed(line):
                issues.append(f"{rel(path)}: example row lacks a detailed teaching explanation")
            prompt = generic_prompt(line)
            if prompt:
                issues.append(f"{rel(path)}: example row contains generic prompt: {prompt}")
            normalized = normalized_explanation(line)
            if len(normalized) >= 80:
                explanation_locations[normalized].append(f"{rel(path)} | {cells[0]}")
            source_kind = example_source_kind(line)
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
