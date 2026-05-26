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


def page_note_content(page: PageRecord, index: int, created: date, display_title: str | None = None) -> str:
    title = display_title or page.title or title_from_url(page.url)
    return "\n".join(
        [
            "---",
            f"title: {yaml_string(title)}",
            f"source_url: {yaml_string(page.url)}",
            f"source_type: {page.kind}",
            f"created: {created.isoformat()}",
            "status: seed",
            "---",
            "",
            f"# {title}",
            "",
            "## 来源",
            "",
            f"- 类型: `{page.kind}`",
            f"- 链接: [{title}]({page.url})",
            "",
            "## 阅读定位",
            "",
            "- 这是一条从网络学习资源自动建立的种子笔记。",
            "- 后续阅读时把核心问题、方法、公式、实验结论和局限补到对应小节。",
            "- 长篇论文、书籍或网页只保留重写后的学习笔记，不复制大段原文。",
            "",
            "## 初步笔记",
            "",
            "- 待补充: 研究问题 / 章节主题。",
            "- 待补充: 关键方法或概念。",
            "- 待补充: 可以复用到自己项目中的做法。",
            "",
            "## 待追问",
            "",
            "- 这个资源解决什么具体问题？",
            "- 方法成立依赖哪些假设？",
            "- 与已有笔记中的哪些主题可以互链？",
            "",
            "## 相关文件",
            "",
            "- [[00_学习地图]]",
            "- [[source_manifest]]",
            "",
        ]
    )


def map_content(title: str, pages: list[PageRecord], note_names: list[str], created: date) -> str:
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
            "- 先保留来源和阅读路径，再逐步补充重写后的解释、公式和实验结论。",
            "- 每个新增观点都尽量回链到来源 URL 或本 vault 中的相关概念笔记。",
            "",
        ]
    )
    return "\n".join(lines)


def create_notes(
    sources: list[str],
    notes_dir: Path,
    *,
    category: str | None = None,
    folder: str | None = None,
    title: str | None = None,
    timeout: float = 15.0,
    dry_run: bool = False,
) -> CreatedNotes:
    pages = collect_sources(sources, timeout=timeout)
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
        content = page_note_content(page, index, today, display_title)
        note_path = available_file(collection_dir / f"{note_name}.md", content)
        note_paths.append(note_path)
        note_names.append(note_path.stem)

    map_path = available_file(collection_dir / "00_学习地图.md", map_content(chosen_title, pages, note_names, today))
    manifest_path = available_file(collection_dir / "source_manifest.md", manifest)
    files = (map_path, manifest_path, *note_paths)

    if not dry_run:
        collection_dir.mkdir(parents=True, exist_ok=True)
        map_path.write_text(map_content(chosen_title, pages, note_names, today), encoding="utf-8")
        manifest_path.write_text(manifest, encoding="utf-8")
        for index, (note_path, page) in enumerate(zip(note_paths, pages), start=1):
            display_title = title if title and len(pages) == 1 else page.title or title_from_url(page.url)
            note_path.write_text(page_note_content(page, index, today, display_title), encoding="utf-8")

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
