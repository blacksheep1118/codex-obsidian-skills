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

GENERIC_PROMPT_PATTERNS = (
    re.compile(r"完整练习：写出题目已知条件"),
    re.compile(r"请说明它对应的知识点，并分析输入或条件改变后的结论变化"),
    re.compile(r"识别变量.{0,20}写步骤.{0,20}解释结果.{0,20}改输入重算"),
)
QUOTED_TOPIC_RE = re.compile(r"“[^”]{1,100}”")


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
    if "解析：" not in line:
        return ""
    explanation = line.split("解析：", 1)[1]
    if "|" in explanation:
        explanation = explanation.split("|", 1)[0]
    return explanation


def compact_explanation(line: str) -> str:
    explanation = explanation_text(line)
    explanation = re.sub(r"`[^`]*`", "", explanation)
    explanation = re.sub(r"<br\s*/?>", " ", explanation)
    return re.sub(r"\s+", "", explanation)


def explanation_is_detailed(line: str) -> bool:
    return len(compact_explanation(line)) >= 30


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
                issues.append(f"{rel(path)}: example row lacks detailed 解析")
            prompt = generic_prompt(line)
            if prompt:
                issues.append(f"{rel(path)}: example row contains generic prompt: {prompt}")
            normalized = normalized_explanation(line)
            if len(normalized) >= 80:
                explanation_locations[normalized].append(f"{rel(path)} | {cells[0]}")
            source_cell = cells[-1]
            generated = "生成：PPT/PDF 未提供独立可抽取例题" in source_cell or "生成辅助题" in line
            source_example = not generated and ("源资料" in source_cell or "源课件例题" in line or "源资料例题" in line)
            if generated:
                generated_examples += 1
            else:
                source_examples += 1
            if generated and "生成：PPT/PDF 未提供独立可抽取例题" not in source_cell:
                issues.append(f"{rel(path)}: generated example missing standard source marker")
            if source_example and "（/" not in line:
                issues.append(f"{rel(path)}: source example missing （/课程/来源） marker")

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
