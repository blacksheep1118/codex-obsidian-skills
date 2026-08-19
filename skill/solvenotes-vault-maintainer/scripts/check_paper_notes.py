#!/usr/bin/env python3
"""Check substantive contracts for paper and paper-topic notes.

This is a lightweight semantic gate.  It checks that a note explains the
research question, method, evidence, boundary, and reproducibility details;
it does not generate an audit directory or rewrite notes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from notes_utils import (
    infer_note_type,
    markdown_files,
    read_text,
    rel,
    strip_frontmatter,
    text_without_code,
)

CONTRACTS = {
    "问题缺口": {
        "heading": ("问题缺口", "研究问题", "问题背景", "要解决", "研究动机", "挑战"),
        "body": ("问题", "缺口", "挑战", "目的", "动机"),
        "minimum": 60,
    },
    "核心方法": {
        "heading": ("核心方法", "方法总览", "核心机制", "网络结构", "模型结构", "方法"),
        "body": ("方法", "模块", "网络", "架构", "framework", "architecture"),
        "minimum": 100,
    },
    "实验结论": {
        "heading": ("实验结论", "实验结果", "实验", "结果", "消融", "性能"),
        "body": ("实验", "结果", "指标", "PSNR", "SSIM", "ablation"),
        "minimum": 60,
    },
    "失败边界": {
        "heading": ("失败边界", "适用边界", "局限", "缺点", "限制", "复习边界", "未解决"),
        "body": ("失败", "局限", "边界", "限制", "缺点", "limitation", "failure"),
        "minimum": 60,
    },
    "可复现要点": {
        "heading": ("可复现要点", "复现", "训练策略", "数据与训练", "实现", "代码"),
        "body": ("复现", "训练", "数据集", "代码", "checkpoint", "config"),
        "minimum": 60,
    },
}
LEGACY_DETAIL_CHARS = 2500


def sections(text: str) -> list[tuple[str, str]]:
    body = strip_frontmatter(text)
    matches = list(re.finditer(r"^#{2,3}\s+(.+?)\s*$", body, re.MULTILINE))
    result: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        result.append((match.group(1).strip(), body[match.end() : end]))
    return result


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text_without_code(text))


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _looks_like_keyword_pile(text: str) -> bool:
    """Reject long text whose apparent detail is only repeated keywords.

    This intentionally targets the adversarial failure mode rather than
    judging prose quality.  Character-level tokenization works for Chinese
    notes and remains deterministic for mixed Chinese/English notes.
    """

    prose = text_without_code(text)
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_+-]*|\d+(?:\.\d+)?|[\u4e00-\u9fff]", prose)
    if len(tokens) < 200:
        return False
    unique = len(set(tokens))
    return unique <= 30 or unique / len(tokens) < 0.08


def paper_contract_gaps(text: str) -> list[str]:
    body = strip_frontmatter(text)
    compact_body = _compact(body)
    note_sections = sections(text)
    gaps: list[str] = []
    for label, contract in CONTRACTS.items():
        explicit = any(
            _contains(heading, contract["heading"])
            and len(_compact(section)) >= contract["minimum"]
            and not _looks_like_keyword_pile(section)
            for heading, section in note_sections
        )
        # Existing long-form paper notes predate the explicit section names.
        # Keep them valid only when the body contains evidence for that topic.
        legacy = (
            len(compact_body) >= LEGACY_DETAIL_CHARS
            and _contains(body, contract["body"])
            and not _looks_like_keyword_pile(body)
        )
        if not explicit and not legacy:
            gaps.append(label)
    return gaps


def paper_paths() -> list:
    return [
        path
        for path in markdown_files()
        if infer_note_type(path) in {"paper_note", "paper_topic_note"}
        and not rel(path).startswith("模板/")
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    issues: list[str] = []
    notes = paper_paths()
    for path in notes:
        gaps = paper_contract_gaps(read_text(path))
        if gaps:
            issues.append(f"{rel(path)}: missing substantive sections: {', '.join(gaps)}")

    payload = {
        "paper_notes": len(notes),
        "paper_contract_issues": len(issues),
        "issues": issues[:100],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"paper_notes {len(notes)}")
        print(f"paper_contract_issues {len(issues)}")
        for issue in issues[:100]:
            print(f"ISSUE {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
