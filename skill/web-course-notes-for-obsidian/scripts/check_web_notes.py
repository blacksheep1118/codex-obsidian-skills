#!/usr/bin/env python3
"""Validate finalized web-course note folders against their source manifest."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import stat
import sys

try:
    from .check_obsidian_links import COMMENT_SPAN_RE, text_without_code
    from .safe_io import ensure_safe_input_directory
    from .url_identity import extract_url_identities, normalize_url
except ImportError:
    from check_obsidian_links import COMMENT_SPAN_RE, text_without_code
    from safe_io import ensure_safe_input_directory
    from url_identity import extract_url_identities, normalize_url


RESIDUE_RE = re.compile(r"(status:\s*scaffold|待补充|TODO|To complete)", re.I)
SKIPPED_RE = re.compile(r"\b(skipped|inaccessible)\b|不可访问|跳过")
DIRECT_RESOURCE_KINDS = {"book", "book_pdf", "pdf", "slides", "transcript"}
READING_LIST_KINDS = {"book_or_chapter", "book", "book_pdf", "pdf"}
MARKDOWN_ESCAPABLE_PUNCTUATION = frozenset(r'''!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~''')
ENTRY_MAP_RE = re.compile(
    r"^00[_ ].*(?:学习地图|课程总览|Learning[_ ]+Map|Course[_ ]+Overview).*\.md$",
    re.I,
)
SUPPORT_NOTE_STEMS = frozenset(
    {
        "agent",
        "agents",
        "readme",
        "source_manifest",
        "99_内容覆盖审查",
        "99_来源覆盖审查",
        "99_质量审查",
        "内容覆盖审查",
        "来源覆盖审查",
        "质量审查",
        "source_coverage_audit",
        "content_coverage_audit",
        "coverage_audit",
        "validation_report",
    }
)
REQUIRED_MANIFEST_HEADERS = {
    "Pages": frozenset({"Kind", "Original Source", "URL"}),
    "Learning Resources": frozenset({"URL", "Access", "Status"}),
}
ALL_MANIFEST_HEADERS = frozenset(
    {
        "Kind",
        "Title",
        "Original Source",
        "URL",
        "Access",
        "Status",
        "Error",
        "Description",
        "Source Page",
        "Final URL",
        "HTTP Status",
        "Access Class",
    }
)
CANONICAL_MANIFEST_HEADERS = {
    header.casefold(): header for header in ALL_MANIFEST_HEADERS
}
ACCESSIBLE_RESOURCE_STATES = frozenset({"accessible", "available", "listed", "ok", "recorded"})
INACCESSIBLE_RESOURCE_STATES = frozenset(
    {
        "blocked",
        "error",
        "failed",
        "inaccessible",
        "login required",
        "network error",
        "parse error",
        "paywalled",
        "skipped",
        "timeout",
        "too large",
    }
)
HTTP_ERROR_STATE_RE = re.compile(r"http [45]\d{2}")
@dataclass(frozen=True)
class ManifestRow:
    section: str
    values: dict[str, str]


@dataclass(frozen=True)
class WebNoteIssue:
    kind: str
    path: Path
    message: str


class ManifestFormatError(ValueError):
    """Raised when a source manifest table cannot be parsed without losing rows."""


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]

    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in stripped:
        if escaped:
            if char in MARKDOWN_ESCAPABLE_PUNCTUATION:
                current.append(char)
            else:
                current.extend(("\\", char))
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if escaped:
        current.append("\\")
    cells.append("".join(current).strip())
    return cells


def has_unescaped_table_delimiter(line: str) -> bool:
    escaped = False
    for char in line:
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            return True
    return False


def is_separator_row(line: str) -> bool:
    return bool(re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", line))


def load_manifest_rows(manifest: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    section: str | None = None
    headers: list[str] | None = None
    separator_seen = False
    seen_sections: set[str] = set()

    def finish_section(section_name: str | None, section_headers: list[str] | None, has_separator: bool) -> None:
        if section_name not in REQUIRED_MANIFEST_HEADERS:
            return
        if section_headers is None:
            raise ManifestFormatError(f"{section_name} section is missing its table header")
        if not has_separator:
            raise ManifestFormatError(f"{section_name} table header is missing its separator row")

    def canonicalize_header(value: str) -> str:
        normalized = " ".join(value.split())
        return CANONICAL_MANIFEST_HEADERS.get(normalized.casefold(), normalized)

    for line_number, raw_line in enumerate(
        manifest.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
    ):
        line = raw_line.strip()
        if line.startswith("## "):
            finish_section(section, headers, separator_seen)
            section = line.removeprefix("## ").strip()
            if section in seen_sections and section in REQUIRED_MANIFEST_HEADERS:
                raise ManifestFormatError(f"line {line_number}: duplicate {section} section")
            seen_sections.add(section)
            headers = None
            separator_seen = False
            continue
        if not line.startswith("|"):
            if line and separator_seen and section in REQUIRED_MANIFEST_HEADERS:
                if has_unescaped_table_delimiter(line):
                    detail = "is missing its leading '|'"
                else:
                    detail = "is missing Markdown table delimiters"
                raise ManifestFormatError(f"line {line_number}: malformed {section} table row {detail}: {line}")
            continue

        cells = split_table_row(line)
        if section is None:
            raise ManifestFormatError(f"line {line_number}: table row appears before a section heading")
        if headers is None:
            if is_separator_row(line):
                raise ManifestFormatError(f"line {line_number}: table separator appears before its header")
            headers = [canonicalize_header(cell) for cell in cells]
            normalized_headers = [" ".join(header.split()).casefold() for header in headers]
            if len(normalized_headers) != len(set(normalized_headers)):
                raise ManifestFormatError(f"line {line_number}: duplicate column name in {section} table header")
            required_headers = REQUIRED_MANIFEST_HEADERS.get(section)
            if required_headers is not None:
                missing_headers = sorted(required_headers.difference(headers))
                if missing_headers:
                    missing = ", ".join(missing_headers)
                    raise ManifestFormatError(
                        f"line {line_number}: {section} table header is missing required columns: {missing}"
                    )
            if any(not header for header in headers):
                raise ManifestFormatError(f"line {line_number}: table header contains an empty column name")
            continue

        if not separator_seen:
            if not is_separator_row(line):
                raise ManifestFormatError(f"line {line_number}: {section} table header is missing its separator row")
            if len(cells) != len(headers):
                raise ManifestFormatError(
                    f"line {line_number}: {section} separator has {len(cells)} cells; expected {len(headers)}"
                )
            separator_seen = True
            continue
        if is_separator_row(line):
            raise ManifestFormatError(f"line {line_number}: duplicate separator row in {section} table")
        if len(cells) != len(headers):
            raise ManifestFormatError(
                f"line {line_number}: {section} row has {len(cells)} cells; expected {len(headers)}"
            )
        values = dict(zip(headers, cells))
        if section == "Pages" and any(not values.get(column, "").strip() for column in ("Kind", "Original Source", "URL")):
            raise ManifestFormatError(
                f"line {line_number}: Pages row has an empty Kind, Original Source, or URL"
            )
        if section == "Learning Resources" and not values.get("URL", "").strip():
            raise ManifestFormatError(f"line {line_number}: Learning Resources row has an empty URL")
        url_columns = {
            "Pages": ("Original Source", "URL"),
            "Learning Resources": ("URL",),
        }.get(section, ())
        for column in url_columns:
            try:
                normalize_url(values[column])
            except ValueError as exc:
                raise ManifestFormatError(
                    f"line {line_number}: {section} {column} has invalid syntax: {exc}"
                ) from exc
        rows.append(ManifestRow(section=section, values=values))

    finish_section(section, headers, separator_seen)
    for required_section in REQUIRED_MANIFEST_HEADERS:
        if required_section not in seen_sections:
            raise ManifestFormatError(f"manifest is missing the {required_section} section and table header")
    return rows


def is_regular_file_without_symlink_components(root: Path, path: Path) -> bool:
    try:
        root_mode = root.lstat().st_mode
    except OSError:
        return False
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        return False
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    current = root
    try:
        for index, component in enumerate(relative.parts):
            current = current / component
            mode = current.lstat().st_mode
            if stat.S_ISLNK(mode):
                return False
            if index < len(relative.parts) - 1 and not stat.S_ISDIR(mode):
                return False
        return stat.S_ISREG(mode)
    except OSError:
        return False


def symlink_issues(root: Path) -> list[WebNoteIssue]:
    issues: list[WebNoteIssue] = []
    try:
        root_mode = root.lstat().st_mode
    except OSError:
        return issues
    if stat.S_ISLNK(root_mode):
        return [
            WebNoteIssue(
                "unsafe_symlink",
                Path("."),
                "finalized collection root must not be a symlink",
            )
        ]
    for path in sorted(root.rglob("*")):
        try:
            is_symlink = stat.S_ISLNK(path.lstat().st_mode)
        except OSError:
            continue
        if is_symlink:
            issues.append(
                WebNoteIssue(
                    "unsafe_symlink",
                    path.relative_to(root),
                    "finalized collection files and directories must not be symlinks",
                )
            )
    return issues


def markdown_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.md")
        if ".git" not in path.parts and is_regular_file_without_symlink_components(root, path)
    )


def is_entry_map(path: Path) -> bool:
    return bool(ENTRY_MAP_RE.match(path.name))


def is_support_note(path: Path) -> bool:
    normalized_stem = re.sub(r"[\s-]+", "_", path.stem.casefold())
    without_collision_suffix = re.sub(r"_\d+$", "", normalized_stem)
    return without_collision_suffix in SUPPORT_NOTE_STEMS


def visible_markdown_text(text: str) -> str:
    """Mask CommonMark code plus HTML/Obsidian comments in one evidence view."""

    code_masked = text_without_code(text)
    assert isinstance(code_masked, str)
    return COMMENT_SPAN_RE.sub(
        lambda match: "".join("\n" if char == "\n" else " " for char in match.group()),
        code_masked,
    )


def has_substantive_markdown_body(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = visible_markdown_text(text).splitlines()
    in_frontmatter = bool(lines and lines[0].strip() == "---")
    for index, line in enumerate(lines):
        stripped = line.strip()
        if in_frontmatter:
            if index > 0 and stripped == "---":
                in_frontmatter = False
            continue
        if not stripped or stripped.startswith("#"):
            continue
        if stripped in {"---", "***", "___"}:
            continue
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            continue
        return True
    return False


def is_detail_note(path: Path) -> bool:
    return not is_entry_map(path) and not is_support_note(path) and has_substantive_markdown_body(path)


def note_files(root: Path) -> list[Path]:
    return [path for path in markdown_files(root) if path.name != "source_manifest.md"]


def manifest_covers_source(rows: list[ManifestRow], source: str) -> bool:
    expected = normalize_url(source)
    page_rows = [row for row in rows if row.section == "Pages"]
    for row in page_rows:
        candidates = [
            row.values.get("Original Source", ""),
            row.values.get("URL", ""),
        ]
        if any(normalize_url(candidate) == expected for candidate in candidates):
            return True
    return False


def file_mentions_url(path: Path, url: str) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    return normalize_url(url) in extract_url_identities(visible_markdown_text(text))


def explicit_skipped_or_inaccessible(path: Path, url: str) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    visible = visible_markdown_text(text)
    return normalize_url(url) in extract_url_identities(visible) and bool(SKIPPED_RE.search(visible))


def manifest_requires_per_link_notes(rows: list[ManifestRow]) -> bool:
    page_rows = [row for row in rows if row.section == "Pages"]
    resource_rows = [row for row in rows if row.section == "Learning Resources"]
    if len(resource_rows) <= 1:
        return False
    page_kinds = {row.values.get("Kind", "") for row in page_rows}
    return bool(page_kinds & READING_LIST_KINDS) or any("reading" in row.values.get("Kind", "") for row in page_rows)


def normalize_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def resource_state_kind(value: str) -> str:
    state = normalize_cell(value).replace("_", " ")
    if state in ACCESSIBLE_RESOURCE_STATES:
        return "accessible"
    if state in INACCESSIBLE_RESOURCE_STATES or HTTP_ERROR_STATE_RE.fullmatch(state):
        return "inaccessible"
    return "unknown"


def inaccessible_resource(row: ManifestRow) -> bool:
    return any(
        resource_state_kind(row.values.get(column, "")) == "inaccessible"
        for column in ("Access", "Status")
    )


def has_contradictory_resource_status(row: ManifestRow) -> bool:
    access = resource_state_kind(row.values.get("Access", ""))
    status = resource_state_kind(row.values.get("Status", ""))
    return access != "unknown" and status != "unknown" and access != status


def validate_web_notes(root: Path, sources: list[str], *, per_link_notes: bool = False) -> list[WebNoteIssue]:
    try:
        root = ensure_safe_input_directory(root)
    except (OSError, ValueError) as exc:
        message = str(exc)
        kind = "unsafe_symlink" if "symlink" in message.casefold() else "invalid_root"
        return [WebNoteIssue(kind, Path("."), message)]
    issues = symlink_issues(root)
    if any(issue.kind == "unsafe_symlink" and issue.path == Path(".") for issue in issues):
        return issues
    manifest = root / "source_manifest.md"
    if not manifest.exists() and not manifest.is_symlink():
        issues.append(WebNoteIssue("missing_manifest", Path("source_manifest.md"), "source_manifest.md is required"))
        return issues
    if not is_regular_file_without_symlink_components(root, manifest):
        issues.append(
            WebNoteIssue(
                "invalid_manifest",
                Path("source_manifest.md"),
                "source_manifest.md must be a regular in-root file reached without symlinks",
            )
        )
        return issues

    try:
        rows = load_manifest_rows(manifest)
    except ManifestFormatError as exc:
        issues.append(WebNoteIssue("invalid_manifest", manifest.relative_to(root), str(exc)))
        return issues
    for source in sources:
        if not manifest_covers_source(rows, source):
            issues.append(WebNoteIssue("missing_user_source", manifest.relative_to(root), f"manifest does not cover user source: {source}"))

    notes = note_files(root)
    entry_maps = [path for path in notes if is_entry_map(path)]
    details = [path for path in notes if is_detail_note(path)]
    if not entry_maps:
        issues.append(
            WebNoteIssue(
                "missing_entry_map",
                Path("."),
                "finalized collection requires an in-root 00_ learning map or course overview",
            )
        )
    if not details:
        issues.append(
            WebNoteIssue(
                "missing_detail_note",
                Path("."),
                "finalized collection requires at least one in-root detailed note",
            )
        )

    learning_rows = [row for row in rows if row.section == "Learning Resources"]
    for row in learning_rows:
        if has_contradictory_resource_status(row):
            issues.append(
                WebNoteIssue(
                    "contradictory_resource_status",
                    manifest.relative_to(root),
                    "learning resource has conflicting Access and Status values "
                    f"({row.values.get('Access', '')!r} vs {row.values.get('Status', '')!r}): "
                    f"{row.values.get('URL', '')}",
                )
            )

    for path in notes:
        text = path.read_text(encoding="utf-8", errors="replace")
        visible = visible_markdown_text(text)
        for line_number, line in enumerate(visible.splitlines(), start=1):
            if RESIDUE_RE.search(line):
                issues.append(
                    WebNoteIssue(
                        "scaffold_residue",
                        path.relative_to(root),
                        f"line {line_number} contains scaffold or unfinished placeholder text",
                    )
                )

    require_per_link = per_link_notes or manifest_requires_per_link_notes(rows)
    if require_per_link:
        resources: list[tuple[str, str]] = []
        seen_resources: set[str] = set()
        for row in learning_rows:
            url = row.values.get("URL", "")
            if has_contradictory_resource_status(row):
                continue
            identity = normalize_url(url)
            if not identity or identity in seen_resources:
                continue
            if inaccessible_resource(row):
                continue
            seen_resources.add(identity)
            resources.append((identity, url))

        note_identities = {
            path: extract_url_identities(
                visible_markdown_text(
                    path.read_text(encoding="utf-8", errors="replace")
                )
            )
            for path in details
        }
        candidates = {
            identity: [
                path for path in details if identity in note_identities[path]
            ]
            for identity, _url in resources
        }
        note_owner: dict[Path, str] = {}

        def assign(identity: str, visited: set[Path]) -> bool:
            for path in candidates[identity]:
                if path in visited:
                    continue
                visited.add(path)
                current = note_owner.get(path)
                if current is None or assign(current, visited):
                    note_owner[path] = identity
                    return True
            return False

        unmatched = {
            identity
            for identity, _url in resources
            if not assign(identity, set())
        }
        for identity, url in resources:
            if identity not in unmatched:
                continue
            issues.append(
                WebNoteIssue(
                    "missing_per_link_note",
                    manifest.relative_to(root),
                    "learning resource has no independently owned detail note or "
                    f"skipped/inaccessible manifest status: {url}",
                )
            )

    return issues


def main() -> int:
    configure_output_encoding()
    parser = argparse.ArgumentParser(description="Check finalized web-course notes against source_manifest.md.")
    parser.add_argument("root", type=Path, help="Collection directory containing source_manifest.md")
    parser.add_argument("--source", action="append", default=[], help="User-supplied source URL or local path; may be repeated")
    parser.add_argument("--per-link-notes", action="store_true", help="Require every learning resource to have a note or explicit skipped/inaccessible status")
    args = parser.parse_args()

    issues = validate_web_notes(args.root, args.source, per_link_notes=args.per_link_notes)
    print(f"web_note_issues {len(issues)}")
    for issue in issues:
        print(f"{issue.kind.upper()}: {issue.path}: {issue.message}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
