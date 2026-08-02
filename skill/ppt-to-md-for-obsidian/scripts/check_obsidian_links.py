#!/usr/bin/env python3
"""Check Markdown and Obsidian wiki links in a vault-like directory."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from urllib.parse import unquote


MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)]+)\)")
WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
FENCE_OPEN_RE = re.compile(r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})[^\n]*$")
FENCE_CLOSE_RE = re.compile(r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})[ \t]*$")
INDENTED_CODE_RE = re.compile(r"^(?: {4}|\t)")


def text_without_code(text: str) -> str:
    """Mask fenced, indented, and inline code while preserving line positions.

    A closing fence may be longer than its opener (CommonMark), so a single
    backreference-based regular expression is not sufficient here.  Scanning
    line-by-line also lets us ignore four-space-indented code blocks.
    """

    def mask(value: str) -> str:
        return "".join("\n" if char == "\n" else " " for char in value)

    masked_lines: list[str] = []
    fence: tuple[str, int] | None = None
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        if fence is not None:
            masked_lines.append(mask(line))
            closing = FENCE_CLOSE_RE.fullmatch(content)
            if (
                closing is not None
                and closing.group("fence")[0] == fence[0]
                and len(closing.group("fence")) >= fence[1]
            ):
                fence = None
            continue

        opening = FENCE_OPEN_RE.fullmatch(content)
        if opening is not None:
            token = opening.group("fence")
            masked_lines.append(mask(line))
            fence = (token[0], len(token))
            continue

        if INDENTED_CODE_RE.match(content):
            masked_lines.append(mask(line))
            continue

        masked_lines.append(mask_inline_code(line))

    return "".join(masked_lines)


def mask_inline_code(line: str) -> str:
    """Mask paired CommonMark backtick code spans on one line.

    Code spans close with a backtick run of the same length as the opener;
    shorter runs may occur inside the span.  Pairing runs explicitly avoids
    treating those interior runs as an early close (which a simple regular
    expression would do).  Unmatched runs are left untouched so links in
    ordinary text are still checked.
    """

    runs: list[tuple[int, int, int]] = []
    index = 0
    while index < len(line):
        if line[index] != "`":
            index += 1
            continue
        end = index + 1
        while end < len(line) and line[end] == "`":
            end += 1
        runs.append((index, end, end - index))
        index = end

    spans: list[tuple[int, int]] = []
    run_index = 0
    while run_index < len(runs) - 1:
        start, _end, length = runs[run_index]
        close_index = next(
            (candidate for candidate in range(run_index + 1, len(runs)) if runs[candidate][2] == length),
            None,
        )
        if close_index is None:
            run_index += 1
            continue
        spans.append((start, runs[close_index][1]))
        run_index = close_index + 1

    if not spans:
        return line
    characters = list(line)
    for start, end in spans:
        for position in range(start, end):
            if characters[position] != "\n":
                characters[position] = " "
    return "".join(characters)


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


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


def is_within_root(root: Path, candidate: Path) -> bool:
    """Return whether a resolved candidate stays inside the vault root."""

    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def resolve_target(root: Path, source: Path, raw_target: str, by_stem: dict[str, list[Path]]) -> list[Path]:
    target = clean_target(raw_target)
    if target is None:
        return []

    if target.startswith("/"):
        target = target.lstrip("/")

    root = root.resolve()
    candidates = []
    for base in (source.parent, root):
        candidate = (base / target).resolve()
        if is_within_root(root, candidate):
            candidates.append(candidate)
        if not target.endswith(".md"):
            candidate = (base / f"{target}.md").resolve()
            if is_within_root(root, candidate):
                candidates.append(candidate)

    if "/" not in target and target in by_stem:
        candidates.extend(
            candidate.resolve()
            for candidate in by_stem[target]
            if is_within_root(root, candidate.resolve())
        )

    resolved = []
    for candidate in candidates:
        if candidate.exists() and candidate not in resolved:
            resolved.append(candidate)
    return resolved


def check_links(root: Path) -> tuple[list[LinkIssue], list[LinkIssue], int]:
    root = root.resolve()
    files: list[Path] = []
    boundary_issues: list[LinkIssue] = []
    for path in sorted(path for path in root.rglob("*") if ".git" not in path.parts):
        if path.is_symlink() and not is_within_root(root, path):
            boundary_issues.append(LinkIssue(path, str(path.resolve()), "outside_root"))
            continue
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        files.append(path)
    by_stem = build_stem_index(files)
    broken: list[LinkIssue] = boundary_issues
    self_links: list[LinkIssue] = []
    checked = 0

    for source in files:
        text = text_without_code(source.read_text(encoding="utf-8", errors="replace"))
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
    configure_output_encoding()
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
