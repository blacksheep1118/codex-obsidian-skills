#!/usr/bin/env python3
"""Find high-confidence template residue and context-sensitive prose candidates.

This checker is deliberately conservative. It reports obvious placeholders
and exact repetition as failures, while generic bridge sentences and repeated
headings remain review candidates. It does not rewrite notes or treat words
such as 保证 and 必然 as errors without context.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from notes_utils import frontmatter_note_type, markdown_files, read_text, rel, text_without_code

PLACEHOLDER_RE = re.compile(r"(?:在此填写|TODO|FIXME|待补充|<待填写>)", re.I)
BOILERPLATE_PATTERNS = (
    ("meta_opening", re.compile(r"本页(?:用于|负责|将介绍)|本篇(?:用于|负责|将介绍)")),
    (
        "learning_outcome",
        re.compile(r"学完本(?:页|篇)(?:后)?\s*[，,]?\s*(?:应能|能够|可以)(?:独立完成)?"),
    ),
    (
        "generic_section",
        re.compile(r"学习目标、前置知识与适用边界|项目验收与面试表达|学完检查"),
    ),
    ("bridge_sentence", re.compile(r"学习完本页后|复习时要把该点放回")),
    ("generic_warning", re.compile(r"不要只背名词|易错点[:：]\s*(?:注意理解|需要理解)")),
    ("generic_summary", re.compile(r"本章内容非常重要")),
)
HEADING_RE = re.compile(r"^#{1,6}\s+")
H2_RE = re.compile(r"^##\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^\s*(\x60{3}|~~~)")
HTML_COMMENT_RE = re.compile(r"^\s*<!--.*-->\s*$")
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+] |\d+[.)]\s+)(.+?)\s*$")
MIN_PARAGRAPH_LENGTH = 24
EXCLUDED_NOTE_TYPES = {"template", "source_manifest", "agent_rule"}
CITATION_RE = re.compile(r"^(?:\[[^]]+\]\(https?://|https?://|DOI[:：]|arXiv[:：])", re.I)
SENTENCE_RE = re.compile(r"[^。！？!?；;]+[。！？!?；;]+|[^。！？!?；;]+$")
REQUIRED_SOURCE_CONTRACT_RE = re.compile(
    r"(?:生成[:：])?PPT/PDF\s*未提供独立可抽取例题[。.]?$"
)


def mask_frontmatter(text: str) -> str:
    """Blank frontmatter while preserving every original source line number."""

    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    body_start = end + len("\n---\n")
    return "\n" * text[:body_start].count("\n") + text[body_start:]


def should_scan(path: Path, text: str) -> bool:
    relative = rel(path)
    if path.name in {"README.md", "AGENT.md", "source_manifest.md"}:
        return False
    if "/.obsidian/templates/" in f"/{relative}":
        return False
    return frontmatter_note_type(text) not in EXCLUDED_NOTE_TYPES


def intentional_heading_schema(relative: str) -> bool:
    return relative.startswith("学习路径/") or relative.startswith("游戏数值策划/表格样例/")


def prose_paragraph_lines(text: str) -> list[list[tuple[int, str]]]:
    """Return prose paragraphs as source-line fragments."""

    paragraphs: list[list[tuple[int, str]]] = []
    lines = text.splitlines()
    current: list[tuple[int, str]] = []
    in_fence = False
    in_math = False

    def flush() -> None:
        nonlocal current
        if current:
            paragraphs.append(current)
            current = []

    for line_number, line in enumerate(lines, 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            flush()
            continue
        stripped = line.strip()
        if not in_fence and stripped == "$$":
            in_math = not in_math
            flush()
            continue
        if in_fence or in_math or not stripped:
            flush()
            continue
        if HTML_COMMENT_RE.match(line):
            flush()
            continue
        if (
            HEADING_RE.match(line)
            or line.lstrip().startswith("|")
            or LIST_ITEM_RE.match(line)
            or line.lstrip().startswith("> ")
        ):
            flush()
            continue
        current.append((line_number, re.sub(r"\s+", " ", stripped)))
    flush()
    return paragraphs


def normalized_paragraphs(text: str) -> list[tuple[int, str]]:
    normalized: list[tuple[int, str]] = []
    for fragments in prose_paragraph_lines(text):
        line = fragments[0][0]
        paragraph = " ".join(fragment for _, fragment in fragments)
        if len(paragraph) < MIN_PARAGRAPH_LENGTH:
            continue
        normalized.append((line, paragraph))
    return normalized


def heading_sequence(text: str) -> tuple[str, ...]:
    """Return the meaningful H2 skeleton without treating code as prose."""

    headings: list[str] = []
    for line in text_without_code(text).splitlines():
        match = H2_RE.match(line.strip())
        if match:
            heading = re.sub(r"\s+", " ", match.group(1)).strip()
            if heading:
                headings.append(heading)
    return tuple(headings)


def first_prose_paragraph(text: str) -> tuple[int, str] | None:
    paragraphs = normalized_paragraphs(text)
    return paragraphs[0] if paragraphs else None


def normalized_sentences(text: str) -> list[tuple[int, str]]:
    """Return prose sentences, joining Markdown soft wraps within paragraphs."""

    sentences: list[tuple[int, str]] = []
    for fragments in prose_paragraph_lines(text):
        offsets: list[tuple[int, int]] = []
        parts: list[str] = []
        cursor = 0
        for line_number, fragment in fragments:
            if parts:
                cursor += 1
            offsets.append((cursor, line_number))
            parts.append(fragment)
            cursor += len(fragment)
        paragraph = " ".join(parts)
        for match in SENTENCE_RE.finditer(paragraph):
            raw_sentence = match.group(0)
            sentence = re.sub(r"\s+", " ", raw_sentence).strip()
            if len(sentence) < MIN_PARAGRAPH_LENGTH:
                continue
            if sentence.startswith(("关联阅读：", "**关联阅读", "来源说明", "**来源说明")):
                continue
            if CITATION_RE.match(sentence) or REQUIRED_SOURCE_CONTRACT_RE.search(sentence):
                continue
            sentence_start = match.start() + len(raw_sentence) - len(raw_sentence.lstrip())
            line_number = offsets[0][1]
            for offset, candidate_line in offsets:
                if offset > sentence_start:
                    break
                line_number = candidate_line
            sentences.append((line_number, sentence))
    return sentences


def normalized_list_items(text: str) -> list[tuple[int, str]]:
    """Return language-like list items, excluding short concept inventories."""

    items: list[tuple[int, str]] = []
    in_fence = False
    for line_number, line in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or HTML_COMMENT_RE.match(line):
            continue
        match = LIST_ITEM_RE.match(line)
        if not match:
            continue
        item = re.sub(r"\s+", " ", match.group(1)).strip()
        if len(item) < MIN_PARAGRAPH_LENGTH:
            continue
        if item.startswith(("http://", "https://", "[[")) or item.startswith(chr(96)):
            continue
        if CITATION_RE.match(item):
            continue
        if not re.search(r"[，。！？：:；;,]", item):
            continue
        items.append((line_number, item))
    return items


def scan() -> dict[str, object]:
    high_confidence: list[dict[str, object]] = []
    review_candidates: list[dict[str, object]] = []
    paragraph_locations: dict[str, list[tuple[str, int]]] = defaultdict(list)
    sentence_locations: dict[str, list[tuple[str, int]]] = defaultdict(list)
    list_locations: dict[str, list[tuple[str, int]]] = defaultdict(list)
    opening_locations: dict[str, list[tuple[str, int]]] = defaultdict(list)
    heading_groups: dict[tuple[str, tuple[str, ...]], list[str]] = defaultdict(list)
    intentional_heading_groups: list[dict[str, object]] = []
    repeated_section_counts: Counter[str] = Counter()
    repeated_section_files: dict[str, set[str]] = defaultdict(set)
    all_files = markdown_files()
    note_files = []

    for path in all_files:
        relative = rel(path)
        text = read_text(path)
        if not should_scan(path, text):
            continue
        note_files.append(path)
        prose = text_without_code(mask_frontmatter(text))
        for line_number, line in enumerate(prose.splitlines(), 1):
            if PLACEHOLDER_RE.search(line):
                high_confidence.append(
                    {"path": relative, "line": line_number, "kind": "placeholder", "context": line.strip()}
                )
            if not (line.lstrip().startswith(">") and "不构成" in line):
                for kind, pattern in BOILERPLATE_PATTERNS:
                    if pattern.search(line):
                        review_candidates.append(
                            {
                                "path": relative,
                                "line": line_number,
                                "kind": kind,
                                "context": line.strip(),
                            }
                        )
                        break
        for line_number, paragraph in normalized_paragraphs(prose):
            if paragraph.startswith(("关联阅读：", "**关联阅读", "来源说明", "**来源说明")):
                continue
            paragraph_locations[paragraph].append((relative, line_number))
        for line_number, sentence in normalized_sentences(prose):
            sentence_locations[sentence].append((relative, line_number))
        for line_number, item in normalized_list_items(prose):
            list_locations[item].append((relative, line_number))
        opening = first_prose_paragraph(prose)
        if opening and not opening[1].startswith(("关联阅读：", "来源说明")):
            opening_locations[opening[1]].append((relative, opening[0]))
        sequence = heading_sequence(mask_frontmatter(text))
        if len(sequence) >= 3:
            heading_groups[(str(path.parent), sequence)].append(relative)
            for heading in sequence:
                if heading in {"学习目标、前置知识与适用边界", "项目验收与面试表达", "学完检查"}:
                    repeated_section_counts[heading] += 1
                    repeated_section_files[heading].add(relative)

    for paragraph, locations in paragraph_locations.items():
        if len(locations) >= 3 and len({path for path, _ in locations}) == 1:
            high_confidence.append(
                {
                    "path": locations[0][0],
                    "line": locations[0][1],
                    "kind": "exact_paragraph_repeat",
                    "count": len(locations),
                    "context": paragraph[:180],
                }
            )
        elif len(locations) >= 5:
            review_candidates.append(
                {
                    "path": locations[0][0],
                    "line": locations[0][1],
                    "kind": "cross_note_paragraph_repeat",
                    "count": len(locations),
                    "files": sorted({path for path, _ in locations}),
                    "context": paragraph[:180],
                }
            )

    for opening, locations in opening_locations.items():
        if len(locations) >= 4:
            review_candidates.append(
                {
                    "path": locations[0][0],
                    "line": locations[0][1],
                    "kind": "repeated_opening",
                    "count": len(locations),
                    "files": sorted({path for path, _ in locations}),
                    "context": opening[:180],
                }
            )

    for sentence, locations in sentence_locations.items():
        distinct_files = {path for path, _ in locations}
        paragraph_occurrences = set(paragraph_locations.get(sentence, []))
        if len(distinct_files) >= 5 and set(locations) != paragraph_occurrences:
            review_candidates.append(
                {
                    "path": locations[0][0],
                    "line": locations[0][1],
                    "kind": "cross_note_sentence_repeat",
                    "count": len(locations),
                    "files": sorted(distinct_files),
                    "context": sentence[:180],
                }
            )

    for item, locations in list_locations.items():
        if len(locations) >= 4:
            review_candidates.append(
                {
                    "path": locations[0][0],
                    "line": locations[0][1],
                    "kind": "repeated_list_item",
                    "count": len(locations),
                    "files": sorted({path for path, _ in locations}),
                    "context": item[:180],
                }
            )

    for (_directory, sequence), locations in heading_groups.items():
        if len(locations) >= 4:
            candidate = {
                "path": locations[0],
                "line": 1,
                "kind": "intentional_heading_schema"
                if all(intentional_heading_schema(path) for path in locations)
                else "structure_reuse",
                "count": len(locations),
                "files": sorted(locations),
                "context": " / ".join(sequence[:8]),
            }
            if candidate["kind"] == "intentional_heading_schema":
                intentional_heading_groups.append(candidate)
            else:
                review_candidates.append(candidate)

    for heading, count in repeated_section_counts.items():
        if count >= 6:
            review_candidates.append(
                {
                    "path": sorted(repeated_section_files[heading])[0],
                    "line": 1,
                    "kind": "repeated_section_heading",
                    "count": count,
                    "files": sorted(repeated_section_files[heading]),
                    "context": heading,
                }
            )

    high_confidence.sort(key=lambda item: (str(item["path"]), int(item["line"])))
    review_candidates.sort(key=lambda item: (str(item["path"]), int(item["line"]), str(item["kind"])))
    review_groups: dict[str, dict[str, object]] = {}
    for item in review_candidates:
        kind = str(item["kind"])
        group = review_groups.setdefault(kind, {"count": 0, "files": set()})
        group["count"] = int(group["count"]) + 1
        group_files = group["files"]
        if isinstance(group_files, set):
            group_files.add(str(item["path"]))
            group_files.update(str(path) for path in item.get("files", []))
    return {
        "files_checked": len(note_files),
        "files_excluded": len(all_files) - len(note_files),
        "naturalness_high_confidence": len(high_confidence),
        "naturalness_review_candidates": len(review_candidates),
        "high_confidence": high_confidence,
        "review_candidates": review_candidates,
        "intentional_structure": intentional_heading_groups,
        "review_groups": {
            kind: {"count": int(value["count"]), "files": sorted(value["files"])}
            for kind, value in sorted(review_groups.items())
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="fail on high-confidence residue")
    args = parser.parse_args()
    payload = scan()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"naturalness_files_checked {payload['files_checked']}")
        print(f"naturalness_high_confidence {payload['naturalness_high_confidence']}")
        print(f"naturalness_review_candidates {payload['naturalness_review_candidates']}")
        for issue in payload["high_confidence"]:
            print(f"HIGH {issue['path']}:{issue['line']} [{issue['kind']}] {issue['context']}")
        for issue in payload["review_candidates"]:
            print(f"REVIEW {issue['path']}:{issue['line']} [{issue['kind']}] {issue['context']}")
        for kind, group in payload["review_groups"].items():
            print(f"REVIEW_GROUP {kind} candidates={group['count']} files={len(group['files'])}")
    return 1 if args.strict and payload["naturalness_high_confidence"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
