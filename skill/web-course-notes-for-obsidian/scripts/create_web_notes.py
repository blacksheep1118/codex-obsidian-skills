#!/usr/bin/env python3
"""Create an Obsidian note folder from web learning resources."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
import sys

from collect_web_sources import PageRecord, build_manifest, collect_sources, title_from_url


CATEGORY_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "计算机视觉",
        (
            "computer vision",
            "cvpr",
            "iccv",
            "eccv",
            "image",
            "video",
            "vision",
            "denois",
            "deblur",
            "dehaze",
            "restoration",
            "segmentation",
            "detection",
        ),
    ),
    ("去雾", ("dehaze", "haze removal", "haze")),
    ("mllm", ("mllm", "multimodal", "vision language", "vlm", "llava", "clip")),
    ("机器学习", ("machine learning", "deep learning", "neural", "optimization", "learning")),
    ("人工智能", ("artificial intelligence", "ai", "agent", "reasoning")),
)

INVALID_PATH_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


@dataclass(frozen=True)
class CreatedNotes:
    collection_dir: Path
    files: tuple[Path, ...]


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def safe_path_name(value: str, fallback: str = "untitled", max_length: int = 80) -> str:
    cleaned = INVALID_PATH_CHARS_RE.sub(" ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned:
        cleaned = fallback
    return cleaned[:max_length].rstrip(" .") or fallback


def yaml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def resolve_language(language: str, pages: list[PageRecord], sources: list[str]) -> str:
    if language in {"zh", "en"}:
        return language
    context = " ".join([*sources, *(page.title for page in pages), *(page.description for page in pages)])
    return "zh" if CJK_RE.search(context) else "en"


def context_for_pages(pages: list[PageRecord]) -> str:
    parts: list[str] = []
    for page in pages:
        parts.extend([page.title, page.url, page.description, page.kind])
        parts.extend(f"{link.title} {link.url} {link.kind}" for link in page.links)
    return " ".join(parts)


def collection_title(pages: list[PageRecord], explicit_title: str | None = None) -> str:
    if explicit_title:
        return explicit_title
    if len(pages) == 1:
        return pages[0].title or title_from_url(pages[0].url)
    first_title = pages[0].title or title_from_url(pages[0].url)
    return f"{first_title} 等 {len(pages)} 个网络资源"


def token_set(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}


def existing_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [path for path in sorted(root.iterdir()) if path.is_dir() and not path.name.startswith(".")]


def choose_category_dir(notes_dir: Path, context: str, explicit_category: str | None = None) -> Path:
    if explicit_category:
        category = Path(explicit_category)
        return category if category.is_absolute() else notes_dir / category

    context_lower = context.lower()
    children = existing_dirs(notes_dir)
    child_by_name = {child.name.lower(): child for child in children}

    for category_name, keywords in CATEGORY_HINTS:
        if not any(keyword in context_lower for keyword in keywords):
            continue
        direct = child_by_name.get(category_name.lower())
        if direct:
            return direct

    context_tokens = token_set(context)
    best_child: Path | None = None
    best_score = 0
    for child in children:
        score = len(token_set(child.name) & context_tokens)
        if score > best_score:
            best_child = child
            best_score = score
    if best_child and best_score >= 1:
        return best_child

    return notes_dir / "网络资源"


def available_file(path: Path, content: str) -> Path:
    if not path.exists():
        return path
    try:
        if path.read_text(encoding="utf-8") == content:
            return path
    except OSError:
        pass

    for index in range(2, 100):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not find an available path near {path}")


def page_note_content_zh(page: PageRecord, index: int, created: date, display_title: str | None = None) -> str:
    title = display_title or page.title or title_from_url(page.url)
    description = page.description.strip() if page.description.strip() else "待补充: 摘要、课程简介或章节定位。"
    lines = [
        "---",
        f"title: {yaml_string(title)}",
        f"source_url: {yaml_string(page.url)}",
        f"source_type: {page.kind}",
        f"note_index: {index}",
        f"created: {created.isoformat()}",
        "status: scaffold",
        "---",
        "",
        f"# {title}",
        "",
        "<!-- scaffold: read or extract the accessible source, then replace every 待补充 item before final delivery. -->",
        "",
        "## 相关",
        "",
        "- [[00_学习地图]]",
        "- [[source_manifest]]",
        "",
        "## 导航",
        "",
        "- 上级入口: [[00_学习地图]]",
        "- 建议阅读顺序: 先看`问题背景`，再看`方法总览`、`关键机制`和`关键公式与变量`，最后用`精简复习`检查理解。",
        "",
        "## 来源",
        "",
        f"- 类型: `{page.kind}`",
        f"- 主链接: [{title}]({page.url})",
        f"- 来源描述: {description}",
    ]

    if page.links:
        lines.extend(["", "### 发现的相关链接", ""])
        for link in page.links:
            lines.append(f"- `{link.kind}` [{link.title}]({link.url})")

    lines.extend(
        [
            "",
            "## 材料定位",
            "",
            "- 待补充: 这份材料属于课程、论文、章节、讲义、项目文档还是资源列表。",
            "- 待补充: 目标读者、前置知识和阅读这份材料的收益。",
            "- 待补充: 与本 vault 中哪些已有主题最相关，并在首次出现处建立链接。",
            "",
            "## 问题背景",
            "",
            "- 待补充: 材料试图解决的核心问题是什么。",
            "- 待补充: 这个问题为什么重要，常见应用场景是什么。",
            "- 待补充: 传统做法或已有方法在哪些条件下不够好。",
            "",
            "## 方法总览",
            "",
            "1. 待补充: 用一句话概括主方法或主线思路。",
            "2. 待补充: 列出输入、输出、关键假设和主要处理阶段。",
            "3. 待补充: 说明方法的创新点、课程主线或章节贡献。",
            "",
            "## 关键机制",
            "",
            "### 机制一: 待命名",
            "",
            "- 待补充: 机制的直觉解释。",
            "- 待补充: 它解决了背景问题中的哪个困难。",
            "- 待补充: 它依赖什么数据、参数、结构或步骤。",
            "",
            "### 机制二: 待命名",
            "",
            "- 待补充: 机制的直觉解释。",
            "- 待补充: 与机制一如何配合。",
            "- 待补充: 可能失败或不适用的情况。",
            "",
            "### 机制三: 可选",
            "",
            "- 待补充: 若材料还有实验设计、训练策略、推理流程或工程实现，在这里展开。",
            "",
            "## 关键公式与变量",
            "",
            "$$",
            "\\text{待补充: 写入核心公式，而不是只写公式编号。}",
            "$$",
            "",
            "- 待补充: 每个变量、张量、集合、概率项或超参数的含义。",
            "- 待补充: 公式从哪一步推来，直觉是什么。",
            "- 待补充: 公式成立需要哪些条件或近似。",
            "",
            "## 实验与案例",
            "",
            "- 待补充: 数据集、任务、评价指标或案例来源。",
            "- 待补充: 主要结果说明了什么，不只记录数值。",
            "- 待补充: 消融、对比实验或失败案例揭示了什么。",
            "",
            "## 方法比较",
            "",
            "| 对比维度 | 本资源方法或观点 | 相关方法或已有笔记 | 影响 |",
            "| --- | --- | --- | --- |",
            "| 问题设定 | 待补充 | 待补充 | 待补充 |",
            "| 核心假设 | 待补充 | 待补充 | 待补充 |",
            "| 优势场景 | 待补充 | 待补充 | 待补充 |",
            "| 局限场景 | 待补充 | 待补充 | 待补充 |",
            "",
            "## 优点",
            "",
            "- 待补充: 方法、课程解释或章节组织最有价值的地方。",
            "- 待补充: 为什么这些优点对实际学习、研究或项目有帮助。",
            "",
            "## 缺点",
            "",
            "- 待补充: 假设过强、信息缺失、实验不足、推导跳步或工程成本。",
            "- 待补充: 使用这份材料时需要警惕的误解。",
            "",
            "## 未解决的问题",
            "",
            "- 待补充: 材料没有回答但后续应该追问的问题。",
            "- 待补充: 可以继续阅读的论文、章节、课程或 vault 内部主题。",
            "",
            "## 复现或应用要点",
            "",
            "- 待补充: 若要复现方法，需要哪些数据、工具、模型、参数或环境。",
            "- 待补充: 若用于自己的项目，最小可行步骤是什么。",
            "- 待补充: 哪些细节会影响结果稳定性。",
            "",
            "## 精简复习",
            "",
            "- 一句话总结: 待补充。",
            "- 三个关键词: 待补充 / 待补充 / 待补充。",
            "- 最容易混淆的点: 待补充。",
            "- 考前或复盘时优先回看: 待补充。",
            "",
            "## 读完后应该能回答的问题",
            "",
            "- 这个资源解决什么具体问题？",
            "- 方法或章节主线的关键假设是什么？",
            "- 最重要的公式、变量或流程分别代表什么？",
            "- 它相对相关方法好在哪里，又在哪些场景会失效？",
            "- 这份材料应当链接到 vault 中哪些已有主题？",
            "",
            "## 相关文件",
            "",
            "- [[00_学习地图]]",
            "- [[source_manifest]]",
            "",
        ]
    )
    return "\n".join(lines)


def page_note_content_en(page: PageRecord, index: int, created: date, display_title: str | None = None) -> str:
    title = display_title or page.title or title_from_url(page.url)
    description = page.description.strip() if page.description.strip() else "To complete: summary, course context, or chapter role."
    lines = [
        "---",
        f"title: {yaml_string(title)}",
        f"source_url: {yaml_string(page.url)}",
        f"source_type: {page.kind}",
        f"access_status: {page.access_status}",
        f"note_index: {index}",
        f"created: {created.isoformat()}",
        "status: scaffold",
        "---",
        "",
        f"# {title}",
        "",
        "<!-- scaffold: read or extract the accessible source, then replace every placeholder before final delivery. -->",
        "",
        "## Related",
        "",
        "- [[00_学习地图]]",
        "- [[source_manifest]]",
        "",
        "## Navigation",
        "",
        "- Parent entry: [[00_学习地图]]",
        "- Suggested order: background, core idea, mechanisms, formulas or evidence, limitations, then review.",
        "",
        "## Source",
        "",
        f"- Type: `{page.kind}`",
        f"- Access status: `{page.access_status}`",
        f"- Main link: [{title}]({page.url})",
        f"- Source description: {description}",
    ]
    if page.error:
        lines.append(f"- Access error: {page.error}")

    if page.links:
        lines.extend(["", "### Discovered Learning Links", ""])
        for link in page.links:
            lines.append(f"- `{link.kind}` [{link.title}]({link.url})")

    lines.extend(
        [
            "",
            "## Source Role",
            "",
            "- To complete: identify whether this is a course, paper, chapter, slide deck, documentation page, or resource list.",
            "- To complete: state the target reader, prerequisites, and why this source matters.",
            "- To complete: connect this source to existing vault topics.",
            "",
            "## Problem Background",
            "",
            "- To complete: the concrete problem this source addresses.",
            "- To complete: why the problem matters and where it appears.",
            "- To complete: what prior or simpler approaches miss.",
            "",
            "## Core Idea",
            "",
            "1. To complete: summarize the main idea in one sentence.",
            "2. To complete: list inputs, outputs, assumptions, and main stages.",
            "3. To complete: explain the source's contribution or learning value.",
            "",
            "## Key Mechanisms",
            "",
            "### Mechanism One",
            "",
            "- To complete: intuitive explanation.",
            "- To complete: what difficulty it solves.",
            "- To complete: required data, parameters, structure, or steps.",
            "",
            "### Mechanism Two",
            "",
            "- To complete: intuitive explanation.",
            "- To complete: how it interacts with the first mechanism.",
            "- To complete: failure cases or limits.",
            "",
            "## Formulas Or Evidence",
            "",
            "$$",
            "\\text{To complete: insert the core formula or evidence pattern when present.}",
            "$$",
            "",
            "- To complete: variable meanings, assumptions, and intuition.",
            "- To complete: source evidence, datasets, examples, or chapter references.",
            "",
            "## Comparison",
            "",
            "| Dimension | This source | Related method or note | Impact |",
            "| --- | --- | --- | --- |",
            "| Problem setting | To complete | To complete | To complete |",
            "| Assumptions | To complete | To complete | To complete |",
            "| Strengths | To complete | To complete | To complete |",
            "| Limits | To complete | To complete | To complete |",
            "",
            "## Limitations",
            "",
            "- To complete: missing evidence, narrow assumptions, implementation cost, or reading gaps.",
            "- To complete: what a reader should verify before relying on this source.",
            "",
            "## Reproduction Or Application Notes",
            "",
            "- To complete: data, tools, models, parameters, or environment needed.",
            "- To complete: minimum practical next step.",
            "- To complete: fragile details that may affect results.",
            "",
            "## Quick Review",
            "",
            "- One-sentence summary: To complete.",
            "- Three keywords: To complete / To complete / To complete.",
            "- Most confusing point: To complete.",
            "- Priority reread section: To complete.",
            "",
            "## Questions To Answer After Reading",
            "",
            "- What specific problem does this source address?",
            "- What assumptions does the main idea require?",
            "- Which formula, evidence, or process matters most?",
            "- Where does this source work well, and where can it fail?",
            "- Which existing vault topics should link here?",
            "",
            "## Related Files",
            "",
            "- [[00_学习地图]]",
            "- [[source_manifest]]",
            "",
        ]
    )
    return "\n".join(lines)


def page_note_content(page: PageRecord, index: int, created: date, display_title: str | None = None, language: str = "zh") -> str:
    if language == "en":
        return page_note_content_en(page, index, created, display_title)
    return page_note_content_zh(page, index, created, display_title)


def map_content_zh(title: str, pages: list[PageRecord], note_names: list[str], created: date) -> str:
    lines = [
        f"# {title}",
        "",
        f"创建日期: {created.isoformat()}",
        "",
        "## 入口笔记",
        "",
    ]
    for note_name in note_names:
        lines.append(f"- [[{note_name}]]")

    lines.extend(["", "## 来源清单", ""])
    for page in pages:
        lines.append(f"- `{page.kind}` [{page.title}]({page.url})")

    lines.extend(
        [
            "",
            "## 整理原则",
            "",
            "- `create_web_notes.py` 只负责建立目录、来源清单和详细脚手架，脚手架不能作为最终笔记交付。",
            "- 先读取或抽取可访问的来源内容，再把脚手架扩写成与目标分类下既有笔记密度一致的学习笔记。",
            "- 每个新增观点都尽量回链到来源 URL 或本 vault 中的相关概念笔记。",
            "- 长篇论文、书籍或网页只保留重写后的学习笔记，不复制大段原文。",
            "",
            "## 完成标准",
            "",
            "- 主笔记不再包含脚手架状态、中文占位词或未完成标记。",
            "- `问题背景`、`方法总览`、`关键机制`、`关键公式与变量`、`实验与案例`、`方法比较`和`精简复习`都有实质内容。",
            "- 关键公式解释了变量含义、直觉、适用条件和局限。",
            "- `source_manifest.md` 覆盖用户提供的每个 URL，最终笔记中的关键判断能追溯到来源。",
            "- 完成后用 vault link checker 检查本文件夹或整个 notes 目录。",
            "",
        ]
    )
    return "\n".join(lines)


def map_content_en(title: str, pages: list[PageRecord], note_names: list[str], created: date) -> str:
    lines = [
        f"# {title}",
        "",
        f"Created: {created.isoformat()}",
        "",
        "## Entry Notes",
        "",
    ]
    for note_name in note_names:
        lines.append(f"- [[{note_name}]]")

    lines.extend(["", "## Source List", ""])
    for page in pages:
        lines.append(f"- `{page.kind}` `{page.access_status}` [{page.title}]({page.url})")

    lines.extend(
        [
            "",
            "## Organization Rules",
            "",
            "- `create_web_notes.py` only creates the folder, source manifest, and detailed scaffolds. Scaffolds are not final deliverables.",
            "- Read or extract accessible source content before replacing placeholders with finished study notes.",
            "- Keep source URLs near claims and connect new concepts to existing vault notes.",
            "- For books and long pages, write transformed study notes rather than copying long passages.",
            "",
            "## Completion Standard",
            "",
            "- Main notes no longer contain scaffold status, placeholder phrases, or unfinished markers.",
            "- Background, core idea, mechanisms, formulas or evidence, comparison, limitations, and quick review contain source-specific content.",
            "- `source_manifest.md` covers every user-provided URL and records inaccessible sources.",
            "- Final delivery has run `scripts/check_web_notes.py` plus the vault link checker when applicable.",
            "",
        ]
    )
    return "\n".join(lines)


def map_content(title: str, pages: list[PageRecord], note_names: list[str], created: date, language: str = "zh") -> str:
    if language == "en":
        return map_content_en(title, pages, note_names, created)
    return map_content_zh(title, pages, note_names, created)


def create_notes(
    sources: list[str],
    notes_dir: Path,
    *,
    category: str | None = None,
    folder: str | None = None,
    title: str | None = None,
    timeout: float = 15.0,
    language: str = "zh",
    dry_run: bool = False,
) -> CreatedNotes:
    pages = collect_sources(sources, timeout=timeout)
    resolved_language = resolve_language(language, pages, sources)
    today = date.today()
    chosen_title = collection_title(pages, title)
    category_dir = choose_category_dir(notes_dir, f"{chosen_title} {context_for_pages(pages)}", category)
    folder_name = safe_path_name(folder or chosen_title, "web-resource")
    collection_dir = category_dir / folder_name

    manifest = build_manifest(pages)
    note_paths: list[Path] = []
    note_names: list[str] = []
    for index, page in enumerate(pages, start=1):
        display_title = title if title and len(pages) == 1 else page.title or title_from_url(page.url)
        note_title = safe_path_name(display_title, f"source-{index}")
        note_name = f"{index:02d}_{note_title}"
        content = page_note_content(page, index, today, display_title, resolved_language)
        note_path = available_file(collection_dir / f"{note_name}.md", content)
        note_paths.append(note_path)
        note_names.append(note_path.stem)

    map_body = map_content(chosen_title, pages, note_names, today, resolved_language)
    map_path = available_file(collection_dir / "00_学习地图.md", map_body)
    manifest_path = available_file(collection_dir / "source_manifest.md", manifest)
    files = (map_path, manifest_path, *note_paths)

    if not dry_run:
        collection_dir.mkdir(parents=True, exist_ok=True)
        map_path.write_text(map_body, encoding="utf-8")
        manifest_path.write_text(manifest, encoding="utf-8")
        for index, (note_path, page) in enumerate(zip(note_paths, pages), start=1):
            display_title = title if title and len(pages) == 1 else page.title or title_from_url(page.url)
            note_path.write_text(page_note_content(page, index, today, display_title, resolved_language), encoding="utf-8")

    return CreatedNotes(collection_dir=collection_dir, files=files)


def main() -> int:
    configure_output_encoding()
    parser = argparse.ArgumentParser(description="Create an Obsidian note folder from web learning resource URLs.")
    parser.add_argument("sources", nargs="+", help="URL or local HTML file")
    parser.add_argument("--notes-dir", type=Path, required=True, help="Existing Obsidian notes directory")
    parser.add_argument("--category", help="Existing or new top-level category folder under --notes-dir")
    parser.add_argument("--folder", help="Collection folder name under the selected category")
    parser.add_argument("--title", help="Title used for 00_学习地图.md")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    parser.add_argument("--language", choices=["zh", "en", "auto"], default="zh", help="Scaffold language. Defaults to zh for backward-compatible Chinese scaffolds.")
    parser.add_argument("--dry-run", action="store_true", help="Print target paths without writing files")
    args = parser.parse_args()

    try:
        created = create_notes(
            args.sources,
            args.notes_dir,
            category=args.category,
            folder=args.folder,
            title=args.title,
            timeout=args.timeout,
            language=args.language,
            dry_run=args.dry_run,
        )
    except OSError as exc:
        print(f"ERROR: failed to create web notes: {exc}", file=sys.stderr)
        return 1

    action = "would_create" if args.dry_run else "created"
    print(f"{action}_web_notes {created.collection_dir}")
    for path in created.files:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
