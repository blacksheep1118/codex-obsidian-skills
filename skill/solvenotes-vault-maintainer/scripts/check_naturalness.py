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
from collections import defaultdict

from notes_utils import markdown_files, read_text, rel, strip_frontmatter, text_without_code

PLACEHOLDER_RE = re.compile(r"(?:在此填写|TODO|FIXME|待补充|<待填写>)", re.I)
BOILERPLATE_RE = re.compile(
    r"(?:本页(?:用于|负责|将介绍)|学习完本页后|复习时要把该点放回|"
    r"不要只背名词|易错点[:：]\s*(?:注意理解|需要理解)|本章内容非常重要)"
)
HEADING_RE = re.compile(r"^#{1,6}\s+")
FENCE_RE = re.compile(r"^\s*(\x60{3}|~~~)")
HTML_COMMENT_RE = re.compile(r"^\s*<!--.*-->\s*$")
MIN_PARAGRAPH_LENGTH = 24


def normalized_paragraphs(text: str) -> list[tuple[int, str]]:
    paragraphs: list[tuple[int, str]] = []
    lines = text.splitlines()
    current: list[str] = []
    start = 1
    in_fence = False
    for line_number, line in enumerate(lines, 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            if current:
                paragraphs.append((start, " ".join(current).strip()))
                current = []
            continue
        if in_fence or not line.strip():
            if current:
                paragraphs.append((start, " ".join(current).strip()))
                current = []
            start = line_number + 1
            continue
        if HTML_COMMENT_RE.match(line):
            if current:
                paragraphs.append((start, " ".join(current).strip()))
                current = []
            start = line_number + 1
            continue
        if HEADING_RE.match(line) or line.lstrip().startswith(("|", "- ", "* ", "> ")):
            if current:
                paragraphs.append((start, " ".join(current).strip()))
                current = []
            start = line_number + 1
            continue
        if not current:
            start = line_number
        current.append(line.strip())
    if current:
        paragraphs.append((start, " ".join(current).strip()))
    normalized: list[tuple[int, str]] = []
    for line, paragraph in paragraphs:
        paragraph = re.sub(r"\s+", " ", paragraph)
        if len(paragraph) < MIN_PARAGRAPH_LENGTH:
            continue
        if paragraph.lstrip().startswith("$$") and paragraph.rstrip().endswith("$$"):
            continue
        normalized.append((line, paragraph))
    return normalized


def scan() -> dict[str, object]:
    high_confidence: list[dict[str, object]] = []
    review_candidates: list[dict[str, object]] = []
    paragraph_locations: dict[str, list[tuple[str, int]]] = defaultdict(list)
    files = markdown_files()

    for path in files:
        relative = rel(path)
        text = read_text(path)
        prose = text_without_code(strip_frontmatter(text))
        for line_number, line in enumerate(prose.splitlines(), 1):
            if PLACEHOLDER_RE.search(line):
                high_confidence.append(
                    {"path": relative, "line": line_number, "kind": "placeholder", "context": line.strip()}
                )
            if BOILERPLATE_RE.search(line) and not (
                line.lstrip().startswith(">") and "不构成" in line
            ):
                review_candidates.append(
                    {"path": relative, "line": line_number, "kind": "boilerplate", "context": line.strip()}
                )
        for line_number, paragraph in normalized_paragraphs(prose):
            if paragraph.startswith(("关联阅读：", "**关联阅读", "来源说明", "**来源说明")):
                continue
            paragraph_locations[paragraph].append((relative, line_number))

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

    high_confidence.sort(key=lambda item: (str(item["path"]), int(item["line"])))
    review_candidates.sort(key=lambda item: (str(item["path"]), int(item["line"]), str(item["kind"])))
    return {
        "files_checked": len(files),
        "naturalness_high_confidence": len(high_confidence),
        "naturalness_review_candidates": len(review_candidates),
        "high_confidence": high_confidence[:100],
        "review_candidates": review_candidates[:200],
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
    return 1 if args.strict and payload["naturalness_high_confidence"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
