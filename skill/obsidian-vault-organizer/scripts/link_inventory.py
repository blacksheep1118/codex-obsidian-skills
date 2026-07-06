#!/usr/bin/env python3
"""Inventory Markdown, wiki, and external links in an Obsidian-style vault."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote


MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)]+)\)")
WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
EXTERNAL_URL_RE = re.compile(r"\b(?:https?://|mailto:)[^\s<>)\]]+")


@dataclass(frozen=True)
class FileInventory:
    file: str
    directory: str
    markdown_links: list[str]
    wiki_links: list[str]
    external_links: list[str]
    unique_targets: list[str]
    counts: dict[str, int]


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def markdown_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.md") if ".git" not in path.parts)


def is_external(target: str) -> bool:
    stripped = target.strip()
    return stripped.startswith(("http://", "https://", "mailto:", "obsidian://"))


def clean_target(target: str) -> str:
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return unquote(target.split("#", 1)[0].split("?", 1)[0]).strip()


def inventory_file(root: Path, path: Path) -> FileInventory:
    text = path.read_text(encoding="utf-8", errors="replace")
    markdown_links: list[str] = []
    wiki_links: list[str] = []
    external_links: list[str] = []

    for match in MARKDOWN_LINK_RE.finditer(text):
        target = match.group(1).strip()
        if is_external(target):
            external_links.append(target)
            continue
        cleaned = clean_target(target)
        if cleaned:
            markdown_links.append(cleaned)

    for match in WIKI_LINK_RE.finditer(text):
        target = clean_target(match.group(1))
        if target:
            wiki_links.append(target)

    for match in EXTERNAL_URL_RE.finditer(text):
        target = match.group(0).rstrip(".,;")
        if target not in external_links:
            external_links.append(target)

    unique_targets = sorted(set(markdown_links + wiki_links + external_links))
    relative = path.relative_to(root)
    counts = {
        "markdown_links": len(markdown_links),
        "wiki_links": len(wiki_links),
        "external_links": len(external_links),
        "unique_targets": len(unique_targets),
        "total_links": len(markdown_links) + len(wiki_links) + len(external_links),
    }
    return FileInventory(
        file=str(relative),
        directory=str(relative.parent) if str(relative.parent) != "." else ".",
        markdown_links=markdown_links,
        wiki_links=wiki_links,
        external_links=external_links,
        unique_targets=unique_targets,
        counts=counts,
    )


def build_inventory(root: Path) -> dict:
    files = [inventory_file(root, path) for path in markdown_files(root)]
    totals = {
        "files": len(files),
        "markdown_links": sum(item.counts["markdown_links"] for item in files),
        "wiki_links": sum(item.counts["wiki_links"] for item in files),
        "external_links": sum(item.counts["external_links"] for item in files),
        "unique_targets": len({target for item in files for target in item.unique_targets}),
        "total_links": sum(item.counts["total_links"] for item in files),
    }
    directories: dict[str, dict[str, int]] = {}
    for item in files:
        counts = directories.setdefault(
            item.directory,
            {"files": 0, "markdown_links": 0, "wiki_links": 0, "external_links": 0, "unique_targets": 0, "total_links": 0},
        )
        counts["files"] += 1
        counts["markdown_links"] += item.counts["markdown_links"]
        counts["wiki_links"] += item.counts["wiki_links"]
        counts["external_links"] += item.counts["external_links"]
        counts["total_links"] += item.counts["total_links"]

    for directory, counts in directories.items():
        targets = {target for item in files if item.directory == directory for target in item.unique_targets}
        counts["unique_targets"] = len(targets)

    return {
        "root": str(root),
        "totals": totals,
        "directories": dict(sorted(directories.items())),
        "files": [asdict(item) for item in files],
    }


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_markdown(inventory: dict) -> str:
    lines = [
        "# Link Inventory",
        "",
        f"- Root: `{inventory['root']}`",
        f"- Files: {inventory['totals']['files']}",
        f"- Total links: {inventory['totals']['total_links']}",
        f"- Markdown links: {inventory['totals']['markdown_links']}",
        f"- Wiki links: {inventory['totals']['wiki_links']}",
        f"- External links: {inventory['totals']['external_links']}",
        f"- Unique targets: {inventory['totals']['unique_targets']}",
        "",
        "## Directory Counts",
        "",
        "| Directory | Files | Markdown | Wiki | External | Unique Targets | Total |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for directory, counts in inventory["directories"].items():
        lines.append(
            f"| {markdown_escape(directory)} | {counts['files']} | {counts['markdown_links']} | {counts['wiki_links']} | "
            f"{counts['external_links']} | {counts['unique_targets']} | {counts['total_links']} |"
        )

    lines.extend(
        [
            "",
            "## File Counts",
            "",
            "| File | Markdown | Wiki | External | Unique Targets | Total |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in inventory["files"]:
        counts = item["counts"]
        lines.append(
            f"| {markdown_escape(item['file'])} | {counts['markdown_links']} | {counts['wiki_links']} | "
            f"{counts['external_links']} | {counts['unique_targets']} | {counts['total_links']} |"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    configure_output_encoding()
    parser = argparse.ArgumentParser(description="Inventory Markdown, wiki, and external links in a vault.")
    parser.add_argument("root", type=Path, help="Vault or notes directory")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    parser.add_argument("--out", type=Path, help="Output path. Defaults to stdout.")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.exists():
        parser.error(f"directory does not exist: {root}")
    if not root.is_dir():
        parser.error(f"root must be a directory: {root}")

    inventory = build_inventory(root)
    if args.format == "json":
        output = json.dumps(inventory, ensure_ascii=False, indent=2) + "\n"
    else:
        output = render_markdown(inventory)

    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(args.out)
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
