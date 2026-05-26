#!/usr/bin/env python3
"""Check Markdown and Obsidian wiki links in a vault-like directory."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import unquote


MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)]+)\)")
WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")


@dataclass(frozen=True)
class LinkIssue:
    source: Path
    target: str
    kind: str


def is_external(target: str) -> bool:
    stripped = target.strip()
    return (
        not stripped
        or stripped.startswith("#")
        or stripped.startswith("http://")
        or stripped.startswith("https://")
        or stripped.startswith("mailto:")
        or stripped.startswith("obsidian://")
    )


def clean_target(target: str) -> str | None:
    target = target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    if is_external(target):
        return None
    target = target.split("#", 1)[0].split("?", 1)[0]
    target = unquote(target).strip()
    return target or None


def build_stem_index(files: list[Path]) -> dict[str, list[Path]]:
    by_stem: dict[str, list[Path]] = {}
    for path in files:
        by_stem.setdefault(path.stem, []).append(path)
    return by_stem


def resolve_target(root: Path, source: Path, raw_target: str, by_stem: dict[str, list[Path]]) -> list[Path]:
    target = clean_target(raw_target)
    if target is None:
        return []

    if target.startswith("/"):
        target = target.lstrip("/")

    candidates = []
    for base in (source.parent, root):
        candidate = (base / target).resolve()
        candidates.append(candidate)
        if not target.endswith(".md"):
            candidates.append((base / f"{target}.md").resolve())

    if "/" not in target and target in by_stem:
        candidates.extend(by_stem[target])

    resolved = []
    for candidate in candidates:
        if candidate.exists() and candidate not in resolved:
            resolved.append(candidate)
    return resolved


def check_links(root: Path) -> tuple[list[LinkIssue], list[LinkIssue], int]:
    files = sorted(path for path in root.rglob("*.md") if ".git" not in path.parts)
    by_stem = build_stem_index(files)
    broken: list[LinkIssue] = []
    self_links: list[LinkIssue] = []
    checked = 0

    for source in files:
        text = source.read_text(encoding="utf-8", errors="replace")
        for regex in (MARKDOWN_LINK_RE, WIKI_LINK_RE):
            for match in regex.finditer(text):
                target = match.group(1)
                if clean_target(target) is None:
                    continue
                checked += 1
                hits = resolve_target(root, source, target, by_stem)
                if not hits:
                    broken.append(LinkIssue(source, target, "broken"))
                elif hits[0] == source.resolve():
                    self_links.append(LinkIssue(source, target, "self"))

    return broken, self_links, checked


def print_issue(root: Path, issue: LinkIssue) -> None:
    source = issue.source.relative_to(root)
    print(f"{issue.kind.upper()}: {source} -> {issue.target}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Obsidian Markdown links.")
    parser.add_argument("root", type=Path, help="Vault or notes directory")
    parser.add_argument("--allow-self-links", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.exists():
        parser.error(f"directory does not exist: {root}")

    broken, self_links, checked = check_links(root)
    print(f"checked_links {checked}")
    print(f"broken_links {len(broken)}")
    print(f"self_links {len(self_links)}")

    for issue in broken:
        print_issue(root, issue)
    if not args.allow_self_links:
        for issue in self_links:
            print_issue(root, issue)

    if broken or (self_links and not args.allow_self_links):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
