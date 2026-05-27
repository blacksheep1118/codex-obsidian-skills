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


def suggested_spine(max_slides: int) -> list[str]:
    base = [
        "Title and research question",
        "Why this problem matters",
        "Gap in existing methods or notes",
        "Main hypothesis or organizing idea",
        "Method overview as a mechanism diagram",
        "Key mechanism 1 with intuition and evidence",
        "Key mechanism 2 with assumptions and failure cases",
        "Core formula or algorithm with variable legend",
        "Data, source, or experimental setup",
        "Main result with annotated proof object",
        "Ablation or comparison matrix",
        "Limitations, risks, and open questions",
        "Implications and discussion prompts",
        "Appendix: derivations, raw tables, extended source material",
    ]
    if max_slides < len(base):
        keep = max(6, max_slides)
        return base[: keep - 2] + ["Limitations and discussion", "Appendix"]
    return base[:max_slides]


def deck_spine(title: str, audience: str, max_slides: int) -> list[str]:
    lines = [
        "",
        "## Suggested Scientific Deck Spine",
        "",
        f"- Title: {title}",
        f"- Audience: {audience}",
        f"- Target main-slide count: {max_slides}",
        "- Style: 科研严谨风; claim-led, evidence-backed, visually inspectable.",
        "",
    ]
    for index, slide in enumerate(suggested_spine(max_slides), start=1):
        lines.append(f"{index}. {slide}")
    return lines


def coverage_checklist() -> list[str]:
    return [
        "",
        "## Coverage Checklist",
        "",
        "- Map every important note section to a slide or appendix item.",
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


def build_brief(inputs: list[Path], title: str | None, audience: str, max_slides: int) -> str:
    files = markdown_files(inputs)
    if not files:
        raise ValueError("no Markdown note files found")
    summaries = [summarize_note(path) for path in files]
    root = find_common_root(files)
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
    lines.extend(deck_spine(deck_title, audience, max_slides))
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
    args = parser.parse_args()

    try:
        brief = build_brief(args.inputs, args.title, args.audience, args.max_slides)
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
