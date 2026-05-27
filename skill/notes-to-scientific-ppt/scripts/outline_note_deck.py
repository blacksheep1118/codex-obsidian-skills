#!/usr/bin/env python3
"""Create a scientific PPT deck brief from Markdown or Obsidian notes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
import os
from pathlib import Path
import re
import sys


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.M)
MD_LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)]+)\)")
WIKI_LINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")
IMAGE_RE = re.compile(r"!\[[^\]\n]*\]\(([^)]+)\)")
MATH_BLOCK_RE = re.compile(r"(?ms)^\s*\$\$\s*$.*?^\s*\$\$\s*$")
URL_RE = re.compile(r"https?://[^\s)>\]]+")
MODE_CHOICES = ("auto", "paper-reading", "proposal", "progress-report", "teaching", "defense")
MODE_LABELS = {
    "paper-reading": "paper reading",
    "proposal": "research proposal",
    "progress-report": "research progress report",
    "teaching": "technical teaching deck",
    "defense": "research defense",
}
MODE_KEYWORDS = {
    "proposal": (
        "proposal",
        "hypothesis",
        "milestone",
        "risk",
        "expected contribution",
        "计划",
        "方案",
        "假设",
        "里程碑",
        "风险",
        "预期",
    ),
    "progress-report": (
        "progress",
        "status",
        "completed",
        "next step",
        "blocker",
        "log",
        "进展",
        "状态",
        "已完成",
        "下一步",
        "阻塞",
        "实验记录",
    ),
    "teaching": (
        "lecture",
        "teaching",
        "tutorial",
        "example",
        "common mistake",
        "prerequisite",
        "课程",
        "教学",
        "教程",
        "例题",
        "常见错误",
        "前置知识",
    ),
    "defense": (
        "defense",
        "thesis",
        "dissertation",
        "committee",
        "contribution",
        "答辩",
        "学位论文",
        "委员会",
        "贡献",
    ),
    "paper-reading": (
        "paper",
        "related work",
        "method",
        "experiment",
        "ablation",
        "limitation",
        "论文",
        "相关工作",
        "方法",
        "实验",
        "消融",
        "局限",
    ),
}


@dataclass(frozen=True)
class Heading:
    level: int
    text: str


@dataclass(frozen=True)
class NoteSummary:
    path: Path
    title: str
    headings: tuple[Heading, ...]
    markdown_links: tuple[str, ...]
    wiki_links: tuple[str, ...]
    image_count: int
    table_count: int
    math_block_count: int
    word_count: int
    text: str


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def markdown_files(inputs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for input_path in inputs:
        path = input_path.expanduser()
        if path.is_dir():
            files.extend(sorted(candidate for candidate in path.rglob("*.md") if not is_hidden(candidate.relative_to(path))))
        elif path.is_file() and path.suffix.lower() == ".md":
            files.append(path)
    return sorted(dict.fromkeys(files))


def strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5 :]
    return text


def count_tables(text: str) -> int:
    lines = text.splitlines()
    count = 0
    for index in range(len(lines) - 1):
        if lines[index].lstrip().startswith("|") and re.match(r"^\s*\|?\s*:?-{3,}:?\s*\|", lines[index + 1]):
            count += 1
    return count


def summarize_note(path: Path) -> NoteSummary:
    text = strip_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    headings = tuple(Heading(len(mark.group(1)), mark.group(2).strip()) for mark in HEADING_RE.finditer(text))
    title = next((heading.text for heading in headings if heading.level == 1), path.stem)
    markdown_links = tuple(sorted(set(MD_LINK_RE.findall(text) + URL_RE.findall(text))))
    wiki_links = tuple(sorted(set(WIKI_LINK_RE.findall(text))))
    words = re.findall(r"[\w\u4e00-\u9fff]+", text)
    return NoteSummary(
        path=path,
        title=title,
        headings=headings,
        markdown_links=markdown_links,
        wiki_links=wiki_links,
        image_count=len(IMAGE_RE.findall(text)),
        table_count=count_tables(text),
        math_block_count=len(MATH_BLOCK_RE.findall(text)),
        word_count=len(words),
        text=text,
    )


def relative_display(path: Path, common_root: Path | None) -> str:
    if common_root is None:
        return str(path)
    try:
        return str(path.relative_to(common_root))
    except ValueError:
        return str(path)


def find_common_root(paths: list[Path]) -> Path | None:
    if not paths:
        return None
    resolved = [path.resolve() for path in paths]
    return Path(os.path.commonpath([str(path.parent) for path in resolved]))


def source_inventory(summaries: list[NoteSummary], root: Path | None) -> list[str]:
    lines = [
        "## Source Inventory",
        "",
        "| Note | Title | Headings | Links | Figures | Tables | Math blocks | Words |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in summaries:
        link_count = len(summary.markdown_links) + len(summary.wiki_links)
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{relative_display(summary.path, root)}`",
                    summary.title.replace("|", "\\|"),
                    str(len(summary.headings)),
                    str(link_count),
                    str(summary.image_count),
                    str(summary.table_count),
                    str(summary.math_block_count),
                    str(summary.word_count),
                ]
            )
            + " |"
        )
    return lines


def extracted_structure(summaries: list[NoteSummary], root: Path | None) -> list[str]:
    lines = ["", "## Extracted Note Structure", ""]
    for summary in summaries:
        lines.append(f"### {summary.title}")
        lines.append("")
        lines.append(f"- Source: `{relative_display(summary.path, root)}`")
        top_headings = [heading for heading in summary.headings if heading.level <= 3]
        if top_headings:
            lines.append("- Major headings:")
            for heading in top_headings[:16]:
                indent = "  " * max(0, heading.level - 1)
                lines.append(f"  {indent}- {heading.text}")
        if summary.markdown_links:
            lines.append("- Source links:")
            for link in summary.markdown_links[:8]:
                lines.append(f"  - {link}")
        if summary.wiki_links:
            lines.append("- Obsidian links:")
            for link in summary.wiki_links[:8]:
                lines.append(f"  - [[{link}]]")
        lines.append("")
    return lines


def detect_mode(summaries: list[NoteSummary], requested_mode: str) -> str:
    if requested_mode != "auto":
        return requested_mode
    corpus = " ".join(
        [summary.title for summary in summaries]
        + [heading.text for summary in summaries for heading in summary.headings]
        + [summary.text[:1200] for summary in summaries]
    ).lower()
    scored = {
        mode: sum(1 for keyword in keywords if keyword.lower() in corpus)
        for mode, keywords in MODE_KEYWORDS.items()
    }
    best_mode, best_score = max(scored.items(), key=lambda item: item[1])
    return best_mode if best_score > 0 else "paper-reading"


def suggested_spine(max_slides: int, mode: str) -> list[str]:
    spines = {
        "paper-reading": [
            "Title and research question",
            "Why this problem matters",
            "Gap in existing work",
            "Main idea of the paper or note cluster",
            "Method overview as a mechanism diagram",
            "Key mechanism 1 with intuition and evidence",
            "Key mechanism 2 with assumptions and failure cases",
            "Core formula or algorithm with variable legend",
            "Experimental setup and metrics",
            "Main result with annotated proof object",
            "Ablation or comparison matrix",
            "Limitations, risks, and open questions",
            "Implications and discussion prompts",
            "Appendix: derivations, raw tables, extended source material",
        ],
        "proposal": [
            "Title and research hypothesis",
            "Problem and why it matters now",
            "Evidence that the gap is real",
            "Proposed technical approach",
            "Method pipeline and assumptions",
            "Data requirements and evaluation plan",
            "Baselines and success metrics",
            "Milestones and deliverables",
            "Risks, mitigations, and fallback paths",
            "Expected contribution",
            "Decision or feedback needed",
            "Appendix: detailed plan and source notes",
        ],
        "progress-report": [
            "Goal and current status",
            "What changed since the last update",
            "Completed work and evidence",
            "Experiment log and metric movement",
            "Current technical interpretation",
            "Failures, blockers, and likely causes",
            "Next decisions",
            "Near-term plan",
            "Risks and support needed",
            "Appendix: raw results and notes",
        ],
        "teaching": [
            "Topic and learning objective",
            "Why the concept matters",
            "Prerequisite bridge",
            "Core intuition",
            "Mechanism diagram",
            "Worked formula or algorithm",
            "Concrete example",
            "Common mistakes and failure cases",
            "Practice or discussion prompt",
            "Summary and next reading",
            "Appendix: extra derivations",
        ],
        "defense": [
            "Title and thesis question",
            "Contributions at a glance",
            "Problem significance",
            "Related-work gap",
            "Method overview",
            "Key technical contribution 1",
            "Key technical contribution 2",
            "Theoretical or design justification",
            "Experimental evidence",
            "Limitations and validity threats",
            "Future work",
            "Backup appendix index",
        ],
    }
    base = spines[mode]
    if max_slides < len(base):
        keep = max(6, max_slides)
        return base[: keep - 2] + ["Limitations and discussion", "Appendix"]
    return base[:max_slides]


def evidence_labels(summary: NoteSummary) -> list[str]:
    labels: list[str] = []
    heading_text = " ".join(heading.text for heading in summary.headings).lower()
    if summary.math_block_count:
        labels.append(f"{summary.math_block_count} formula block(s)")
    if summary.table_count:
        labels.append(f"{summary.table_count} table(s)")
    if summary.image_count:
        labels.append(f"{summary.image_count} image/figure(s)")
    if summary.markdown_links or summary.wiki_links:
        labels.append(f"{len(summary.markdown_links) + len(summary.wiki_links)} link(s)")
    if any(keyword in heading_text for keyword in ("experiment", "实验", "结果", "result", "ablation", "消融")):
        labels.append("experiment/result section")
    if any(keyword in heading_text for keyword in ("limitation", "局限", "risk", "风险", "failure", "失败")):
        labels.append("limitation/risk section")
    if not labels:
        labels.append("headings/text only")
    return labels


def proof_objects(summary: NoteSummary) -> list[str]:
    objects: list[str] = []
    heading_text = " ".join(heading.text for heading in summary.headings).lower()
    if any(keyword in heading_text for keyword in ("背景", "motivation", "problem", "问题")):
        objects.append("problem contrast")
    if any(keyword in heading_text for keyword in ("方法", "method", "mechanism", "pipeline", "机制")):
        objects.append("mechanism diagram")
    if summary.math_block_count:
        objects.append("equation-to-intuition bridge")
    if summary.table_count:
        objects.append("result/comparison table")
    if summary.image_count:
        objects.append("annotated figure or example panel")
    if any(keyword in heading_text for keyword in ("实验", "experiment", "result", "结果", "ablation", "消融")):
        objects.append("evidence slide")
    if any(keyword in heading_text for keyword in ("局限", "limitation", "risk", "风险", "failure", "失败")):
        objects.append("limitation/failure-case slide")
    if not objects:
        objects.append("claim-and-evidence text slide")
    return objects


def gap_labels(summary: NoteSummary) -> list[str]:
    gaps: list[str] = []
    heading_text = " ".join(heading.text for heading in summary.headings).lower()
    if not (summary.markdown_links or summary.wiki_links):
        gaps.append("no source links detected")
    if not summary.math_block_count and any(keyword in heading_text for keyword in ("公式", "equation", "algorithm", "算法")):
        gaps.append("formula-related heading without math block")
    if not (summary.table_count or summary.image_count) and any(
        keyword in heading_text for keyword in ("实验", "experiment", "result", "结果")
    ):
        gaps.append("evidence heading without table/figure")
    if not any(keyword in heading_text for keyword in ("局限", "limitation", "risk", "风险", "failure", "失败")):
        gaps.append("limitations not explicit")
    if not gaps:
        gaps.append("no obvious structural gaps")
    return gaps


def evidence_ledger(summaries: list[NoteSummary], root: Path | None) -> list[str]:
    lines = [
        "",
        "## Evidence Ledger",
        "",
        "| Note | Evidence present | Candidate proof objects | Assumptions or gaps to verify |",
        "| --- | --- | --- | --- |",
    ]
    for summary in summaries:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{relative_display(summary.path, root)}`",
                    ", ".join(evidence_labels(summary)).replace("|", "\\|"),
                    ", ".join(proof_objects(summary)).replace("|", "\\|"),
                    ", ".join(gap_labels(summary)).replace("|", "\\|"),
                ]
            )
            + " |"
        )
    return lines


def slide_role(heading: Heading) -> str:
    text = heading.text.lower()
    if any(keyword in text for keyword in ("背景", "motivation", "problem", "问题")):
        return "problem framing"
    if any(keyword in text for keyword in ("方法", "method", "mechanism", "pipeline", "机制")):
        return "method/mechanism"
    if any(keyword in text for keyword in ("公式", "equation", "algorithm", "算法")):
        return "formula/algorithm"
    if any(keyword in text for keyword in ("实验", "result", "结果", "ablation", "消融", "评估")):
        return "evidence/results"
    if any(keyword in text for keyword in ("局限", "limitation", "risk", "风险", "failure", "失败")):
        return "limitations"
    if any(keyword in text for keyword in ("总结", "discussion", "讨论", "future", "未来")):
        return "discussion"
    return "supporting concept"


def draft_slide_backlog(summaries: list[NoteSummary], root: Path | None, mode: str) -> list[str]:
    lines = [
        "",
        "## Draft Slide Backlog",
        "",
        f"Use this as a source-grounded backlog for a `{mode}` deck. Convert each item into a claim-title slide or appendix item; do not paste note paragraphs directly.",
        "",
    ]
    item_count = 0
    for summary in summaries:
        source = relative_display(summary.path, root)
        for heading in [heading for heading in summary.headings if 2 <= heading.level <= 3][:10]:
            item_count += 1
            role = slide_role(heading)
            proof = ", ".join(proof_objects(summary)[:2])
            lines.append(
                f"- [{role}] Turn `{heading.text}` into a claim slide or appendix item. Source: `{source}`. Proof object: {proof}."
            )
    if item_count == 0:
        for summary in summaries:
            source = relative_display(summary.path, root)
            proof = ", ".join(proof_objects(summary)[:2])
            lines.append(f"- [supporting concept] Build one claim slide from `{summary.title}`. Source: `{source}`. Proof object: {proof}.")
    return lines


def deck_spine(title: str, audience: str, max_slides: int, mode: str) -> list[str]:
    lines = [
        "",
        "## Suggested Scientific Deck Spine",
        "",
        f"- Title: {title}",
        f"- Audience: {audience}",
        f"- Deck Mode: {mode} ({MODE_LABELS[mode]})",
        f"- Target main-slide count: {max_slides}",
        "- Style: 科研严谨风; claim-led, evidence-backed, visually inspectable.",
        "",
    ]
    for index, slide in enumerate(suggested_spine(max_slides, mode), start=1):
        lines.append(f"{index}. {slide}")
    return lines


def coverage_checklist() -> list[str]:
    return [
        "",
        "## Coverage Checklist",
        "",
        "- Map every important note section to a slide or appendix item.",
        "- Use the evidence ledger to decide proof objects before opening the presentation tool.",
        "- Mark unsupported claims as gaps instead of turning them into slide conclusions.",
        "- Include source note paths or URLs for technical claims.",
        "- Explain formulas with variable definitions, intuition, assumptions, and relevance.",
        "- Include limitations, failure cases, or open questions when present in the notes.",
        "- Ensure every main slide has a claim title and one proof object.",
        "- Render the PPTX preview/contact sheet before final delivery.",
        "",
        "## Missing Inputs To Check",
        "",
        "- Target talk length, if different from the default.",
        "- Audience background and expected technical depth.",
        "- Required template, logo, or institutional style guide.",
        "- Permission to use source figures or screenshots, if needed.",
        "",
    ]


def build_brief(inputs: list[Path], title: str | None, audience: str, max_slides: int, mode: str) -> str:
    files = markdown_files(inputs)
    if not files:
        raise ValueError("no Markdown note files found")
    summaries = [summarize_note(path) for path in files]
    root = find_common_root(files)
    detected_mode = detect_mode(summaries, mode)
    deck_title = title or (summaries[0].title if len(summaries) == 1 else f"{summaries[0].title} 等 {len(summaries)} 篇笔记")
    lines = [
        f"# {deck_title}",
        "",
        f"Created: {date.today().isoformat()}",
        "",
        "This deck brief inventories source notes before building a rigorous scientific PPT. It is a planning artifact, not the final deck.",
        "",
    ]
    lines.extend(source_inventory(summaries, root))
    lines.extend(extracted_structure(summaries, root))
    lines.extend(evidence_ledger(summaries, root))
    lines.extend(deck_spine(deck_title, audience, max_slides, detected_mode))
    lines.extend(draft_slide_backlog(summaries, root, detected_mode))
    lines.extend(coverage_checklist())
    return "\n".join(lines)


def main() -> int:
    configure_output_encoding()
    parser = argparse.ArgumentParser(description="Create a scientific PPT deck brief from Markdown or Obsidian notes.")
    parser.add_argument("inputs", nargs="+", type=Path, help="Markdown note file or directory containing .md files")
    parser.add_argument("--out", type=Path, help="Output deck brief Markdown path")
    parser.add_argument("--title", help="Deck title")
    parser.add_argument("--audience", default="research seminar", help="Target audience or talk context")
    parser.add_argument("--max-slides", type=int, default=18, help="Target main-slide count")
    parser.add_argument("--mode", choices=MODE_CHOICES, default="auto", help="Deck mode; default auto-detects from notes")
    args = parser.parse_args()

    try:
        brief = build_brief(args.inputs, args.title, args.audience, args.max_slides, args.mode)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(brief, encoding="utf-8")
        print(f"wrote_deck_brief {args.out}")
    else:
        print(brief)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
