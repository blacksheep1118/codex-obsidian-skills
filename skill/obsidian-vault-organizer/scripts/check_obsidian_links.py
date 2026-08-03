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
LIST_ITEM_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<marker>[-+*]|\d{1,9}[.)])(?:(?P<spacing>[ \t]+)|$)"
)


@dataclass
class ListContext:
    content_indent: int
    has_body: bool


@dataclass(frozen=True)
class ListItemLayout:
    marker_indent: int
    content_indent: int
    body_index: int
    has_body: bool


@dataclass(frozen=True)
class FenceContext:
    marker: str
    length: int
    quote_depth: int
    list_indents: tuple[int, ...]


def indentation_columns(value: str, start: int = 0) -> int:
    columns = start
    for char in value:
        if char == " ":
            columns += 1
        elif char == "\t":
            columns += 4 - (columns % 4)
        else:
            break
    return columns


def leading_whitespace(line: str) -> tuple[int, int]:
    index = 0
    while index < len(line) and line[index] in " \t":
        index += 1
    return index, indentation_columns(line[:index])


def blockquote_prefix(line: str, max_depth: int | None = None) -> tuple[int, int]:
    """Return explicit CommonMark blockquote depth and consumed character count."""

    depth = 0
    cursor = 0
    while max_depth is None or depth < max_depth:
        marker = cursor
        spaces = 0
        while marker < len(line) and line[marker] == " " and spaces < 3:
            marker += 1
            spaces += 1
        if marker >= len(line) or line[marker] != ">":
            break
        cursor = marker + 1
        if cursor < len(line) and line[cursor] in " \t":
            cursor += 1
        depth += 1
    return depth, cursor


def is_thematic_break(line: str) -> bool:
    whitespace_end, indent = leading_whitespace(line)
    if indent > 3:
        return False
    compact = re.sub(r"[ \t]", "", line[whitespace_end:])
    return len(compact) >= 3 and len(set(compact)) == 1 and compact[0] in "*-_"


def list_item_layout(line: str) -> ListItemLayout | None:
    """Return CommonMark list layout, including empty-marker items."""

    if is_thematic_break(line):
        return None

    match = LIST_ITEM_RE.match(line)
    if match is None:
        return None
    marker_indent = indentation_columns(match.group("indent"))
    marker_end = marker_indent + len(match.group("marker"))
    marker_end_index = len(match.group("indent")) + len(match.group("marker"))
    spacing = match.group("spacing") or ""
    unpadded_body_index = marker_end_index + len(spacing)
    has_body = bool(line[unpadded_body_index:].strip())
    if not has_body:
        # CommonMark gives an empty list item W + 1 columns of padding,
        # regardless of how much trailing whitespace follows its marker.
        padding = 1
        body_index = unpadded_body_index
    elif not spacing:
        padding = 1
        body_index = marker_end_index
    else:
        spacing_end = indentation_columns(spacing, start=marker_end)
        padding = spacing_end - marker_end
        if 1 <= padding <= 4:
            body_index = marker_end_index + len(spacing)
        else:
            padding = 1
            body_index = marker_end_index + 1
    return ListItemLayout(
        marker_indent=marker_indent,
        content_indent=marker_end + padding,
        body_index=body_index,
        has_body=has_body,
    )


def updated_list_stack(
    stack: list[ListContext],
    layout: ListItemLayout,
) -> list[ListContext] | None:
    """Return an updated list-container stack, or None when layout is code text."""

    updated = list(stack)
    while updated and layout.marker_indent < updated[-1].content_indent:
        updated.pop()
    container_indent = updated[-1].content_indent if updated else 0
    if not 0 <= layout.marker_indent - container_indent <= 3:
        return None
    updated.append(
        ListContext(
            content_indent=layout.content_indent,
            has_body=layout.has_body,
        )
    )
    return updated


def list_continuation_view(
    line: str,
    stack: list[ListContext],
    previous_blank: bool,
) -> tuple[str, int, list[ListContext]]:
    """Strip an active list container and return logical content plus prefix width."""

    if not line.strip():
        return "", len(line), stack
    whitespace_end, indent = leading_whitespace(line)
    matching_context = next(
        (index for index in range(len(stack) - 1, -1, -1) if indent >= stack[index].content_indent),
        None,
    )
    if matching_context is not None:
        updated = stack[: matching_context + 1]
        relative_indent = indent - updated[-1].content_indent
        logical = " " * relative_indent + line[whitespace_end:]
        return logical, whitespace_end, updated
    if previous_blank:
        return line, 0, []
    return line, 0, stack


def mask_prefix(value: str, end: int) -> str:
    characters = list(value)
    for position in range(min(end, len(characters))):
        if characters[position] not in "\r\n":
            characters[position] = " "
    return "".join(characters)


def text_without_code(text: str) -> str:
    """Mask CommonMark code and expose non-code container bodies in place.

    A closing fence may be longer than its opener (CommonMark), so a single
    backreference-based regular expression is not sufficient.  The scanner
    removes blockquote and list container prefixes before classifying fenced
    or indented code, while keeping output line and character positions stable.
    """

    def mask(value: str) -> str:
        return "".join("\n" if char == "\n" else " " for char in value)

    masked_lines: list[str] = []
    fence: FenceContext | None = None
    list_stack: list[ListContext] = []
    active_quote_depth = 0
    in_indented_code = False
    previous_blank = True
    for line in text.splitlines(keepends=True):
        raw = line.rstrip("\r\n")

        if fence is not None:
            required_quote_depth = fence.quote_depth
            quote_depth, quote_end = blockquote_prefix(raw, max_depth=required_quote_depth)
            if quote_depth == required_quote_depth:
                content = raw[quote_end:]
                remains_in_list = True
                if fence.list_indents and content.strip():
                    _whitespace_end, indent = leading_whitespace(content)
                    active_indents = tuple(
                        context.content_indent
                        for context in list_stack[: len(fence.list_indents)]
                    )
                    remains_in_list = (
                        active_indents == fence.list_indents
                        and indent >= fence.list_indents[-1]
                    )
                if remains_in_list:
                    logical, _list_prefix, list_stack = list_continuation_view(
                        content,
                        list_stack,
                        previous_blank=False,
                    )
                    masked_lines.append(mask(line))
                    closing = FENCE_CLOSE_RE.fullmatch(logical)
                    if (
                        closing is not None
                        and closing.group("fence")[0] == fence.marker
                        and len(closing.group("fence")) >= fence.length
                    ):
                        fence = None
                    previous_blank = not content.strip()
                    continue

                # A nonblank outdent closes a fence opened in a list. Keep
                # only any outer list containers that the current line still
                # belongs to, then process this same line as ordinary Markdown.
                fence = None
                in_indented_code = False
                _whitespace_end, indent = leading_whitespace(content)
                matching_context = next(
                    (
                        index
                        for index in range(len(list_stack) - 1, -1, -1)
                        if indent >= list_stack[index].content_indent
                    ),
                    None,
                )
                list_stack = (
                    list_stack[: matching_context + 1]
                    if matching_context is not None
                    else []
                )
            else:
                fence = None
                list_stack = []
                in_indented_code = False

        quote_depth, quote_end = blockquote_prefix(raw)
        if quote_depth != active_quote_depth:
            list_stack = []
            in_indented_code = False
            active_quote_depth = quote_depth
        content = raw[quote_end:]
        prefix_end = quote_end
        line_list_indents: tuple[int, ...] = ()

        layout = list_item_layout(content)
        if layout is not None:
            next_stack = updated_list_stack(list_stack, layout)
        else:
            next_stack = None
        if next_stack is not None:
            list_stack = next_stack
            logical = content[layout.body_index:]
            prefix_end = quote_end + layout.body_index
            line_list_indents = tuple(context.content_indent for context in list_stack)
        else:
            logical, list_prefix, list_stack = list_continuation_view(
                content,
                list_stack,
                previous_blank=previous_blank,
            )
            prefix_end = quote_end + list_prefix
            if list_prefix:
                line_list_indents = tuple(context.content_indent for context in list_stack)

        if not logical.strip():
            if in_indented_code:
                masked_lines.append(mask(line))
            else:
                masked_lines.append(mask_prefix(line, prefix_end))
            previous_blank = True
            continue

        opening = FENCE_OPEN_RE.fullmatch(logical)
        if opening is not None:
            token = opening.group("fence")
            masked_lines.append(mask(line))
            if not line_list_indents:
                list_stack = []
            fence = FenceContext(
                marker=token[0],
                length=len(token),
                quote_depth=quote_depth,
                list_indents=line_list_indents,
            )
            in_indented_code = False
            if list_stack:
                list_stack[-1].has_body = True
            previous_blank = False
            continue

        logical_indent = indentation_columns(logical)
        if in_indented_code and logical_indent >= 4:
            masked_lines.append(mask(line))
            previous_blank = False
            continue
        in_indented_code = False

        can_start_indented_code = logical_indent >= 4 and (
            not list_stack or previous_blank or not list_stack[-1].has_body
        )
        if can_start_indented_code:
            masked_lines.append(mask(line))
            in_indented_code = True
            if list_stack:
                list_stack[-1].has_body = True
            previous_blank = False
            continue

        if list_stack:
            list_stack[-1].has_body = True
        masked_lines.append(mask_prefix(mask_inline_code(line), prefix_end))
        previous_blank = False

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
