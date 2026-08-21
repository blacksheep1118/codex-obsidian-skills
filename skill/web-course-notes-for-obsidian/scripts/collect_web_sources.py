#!/usr/bin/env python3
"""Collect a Markdown source manifest from course, slide, and book web pages."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import socket
import sys
import time
from typing import Iterable
from urllib.parse import unquote, urldefrag, urljoin, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, url2pathname, urlopen

try:
    from .safe_io import (
        InputTooLargeError,
        ensure_safe_input_file,
        read_bytes_no_follow,
        safe_write_text,
    )
    from .url_identity import normalize_url
except ImportError:
    from safe_io import (
        InputTooLargeError,
        ensure_safe_input_file,
        read_bytes_no_follow,
        safe_write_text,
    )
    from url_identity import normalize_url


VIDEO_HOST_RE = re.compile(r"(youtube|youtu\.be|bilibili|vimeo|coursera|edx|khanacademy|ocw|mit\.edu)", re.I)
VIDEO_PATH_RE = re.compile(r"(/watch|/video|/lecture|/lesson|/play)", re.I)
SLIDE_EXTENSIONS = (".ppt", ".pptx", ".odp", ".key")
PDF_EXTENSIONS = (".pdf",)
BOOK_EXTENSIONS = (".epub", ".mobi")
TRANSCRIPT_EXTENSIONS = (".vtt", ".srt", ".ttml", ".txt")
BOOK_PATH_RE = re.compile(r"(/book|/books|/chapter|/chapters|/readings?|/textbook)", re.I)
COURSE_PATH_RE = re.compile(r"(/course|/courses|/class|/classes|/syllabus|/module|/modules)", re.I)
DIRECT_RESOURCE_KINDS = {"book", "book_pdf", "pdf", "slides", "transcript"}
STATIC_HELPER_EXTENSIONS = (".js", ".mjs", ".cjs", ".css", ".map", ".wasm")
STATIC_HELPER_LABEL_RE = re.compile(
    r"(?:\bbundle\b|\bsource\s+map\b|\bstylesheet\b|"
    r"\b(?:webassembly|wasm)\s+module\b|\bstatic\s+(?:asset|script)\b)",
    re.I,
)
STATIC_HELPER_BASENAME_RE = re.compile(
    r"^(?:app|main|bundle|runtime|vendor|webpack)(?:[._-][a-z0-9]+)*"
    r"\.(?:js|mjs|cjs|css|map|wasm)$",
    re.I,
)
API_HELPER_PATH_RE = re.compile(r"(?:^|/)(?:api|graphql|wp-json)(?:/|$)", re.I)
API_HELPER_LABEL_RE = re.compile(r"(?:\b(?:api|endpoint|graphql)\b|接口|端点)", re.I)
NAVIGATION_HELPER_LABELS = {
    "open menu",
    "site navigation",
    "站点导航",
}
LOGIN_PAGE_RE = re.compile(
    r"(?:<input[^>]+type=[\"']password|\b(sign\s*in|log\s*in|login|required\s+login)\b|登录|登入)",
    re.I,
)
DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
DEFAULT_TOTAL_TIMEOUT_SECONDS = 30.0
READ_CHUNK_BYTES = 64 * 1024


class SourceTooLargeError(ValueError):
    """Raised when a source exceeds the configured byte budget."""


class SourceTotalTimeoutError(TimeoutError):
    """Raised when reading a source exceeds the total wall-clock budget."""


class LocalSourceAccessError(OSError):
    """Raised when a local source cannot be read without following links."""


@dataclass(frozen=True)
class LinkRecord:
    source: str
    title: str
    url: str
    kind: str
    provenance_only: bool = False


@dataclass(frozen=True)
class PageRecord:
    original_source: str
    canonical_url: str
    title: str
    kind: str
    access_status: str
    description: str
    error: str
    links: tuple[LinkRecord, ...]
    final_url: str = ""
    http_status: int | None = None
    access_class: str = "unknown"

    @property
    def source(self) -> str:
        return self.original_source

    @property
    def url(self) -> str:
        return self.canonical_url


class LearningHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.description = ""
        self.canonical = ""
        self.links: list[tuple[str, str]] = []
        self._in_title = False
        self._active_href = ""
        self._active_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "title":
            self._in_title = True
        elif tag.lower() == "meta" and attrs_map.get("name", "").lower() == "description":
            self.description = attrs_map.get("content", "").strip()
        elif tag.lower() == "link" and attrs_map.get("rel", "").lower() == "canonical":
            self.canonical = attrs_map.get("href", "").strip()
        elif tag.lower() == "a" and attrs_map.get("href"):
            self._active_href = attrs_map["href"].strip()
            self._active_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
        elif tag.lower() == "a" and self._active_href:
            text = normalize_space(" ".join(self._active_text))
            self.links.append((self._active_href, text))
            self._active_href = ""
            self._active_text = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._active_href:
            self._active_text.append(data)

    @property
    def title(self) -> str:
        return normalize_space(" ".join(self.title_parts))


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https", "file"}


def source_to_url(source: str) -> str:
    if is_url(source):
        return normalize_url(source)
    return Path(os.path.abspath(Path(source).expanduser())).as_uri()


def title_from_url(url: str) -> str:
    parsed = urlparse(url)
    path_name = Path(unquote(parsed.path)).name
    if not path_name:
        return parsed.netloc or url
    stem = Path(path_name).stem
    return normalize_space(re.sub(r"[_-]+", " ", stem)) or path_name


def _read_limited(stream: object, *, max_bytes: int, deadline: float) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        now = time.monotonic()
        if now >= deadline:
            raise SourceTotalTimeoutError("source read exceeded the total time budget")
        _set_stream_timeout(stream, deadline - now)
        chunk = stream.read(min(READ_CHUNK_BYTES, max_bytes - total + 1))
        if time.monotonic() >= deadline:
            raise SourceTotalTimeoutError("source read exceeded the total time budget")
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > max_bytes:
            raise SourceTooLargeError(f"source exceeds byte limit ({max_bytes} bytes)")
        chunks.append(chunk)


def _set_stream_timeout(stream: object, remaining: float) -> None:
    """Best-effort socket deadline tightening for urllib response streams."""

    current = stream
    for attribute in ("fp", "raw", "_sock"):
        setter = getattr(current, "settimeout", None)
        if callable(setter):
            setter(remaining)
            return
        current = getattr(current, attribute, None)
        if current is None:
            return
    setter = getattr(current, "settimeout", None)
    if callable(setter):
        setter(remaining)


def read_source_with_metadata(
    source_url: str,
    timeout: float = 15.0,
    *,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    total_timeout: float = DEFAULT_TOTAL_TIMEOUT_SECONDS,
) -> tuple[str, str, int | None]:
    if timeout <= 0 or total_timeout <= 0:
        raise ValueError("timeout budgets must be positive")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    parsed = urlparse(source_url)
    if parsed.scheme == "file":
        try:
            source_path = ensure_safe_input_file(Path(url2pathname(parsed.path)))
        except (OSError, ValueError) as exc:
            raise LocalSourceAccessError(str(exc)) from exc
        deadline = time.monotonic() + total_timeout
        try:
            payload = read_bytes_no_follow(source_path, max_bytes=max_bytes)
        except InputTooLargeError as exc:
            raise SourceTooLargeError(str(exc)) from exc
        except (OSError, ValueError) as exc:
            raise LocalSourceAccessError(str(exc)) from exc
        if time.monotonic() >= deadline:
            raise SourceTotalTimeoutError("source read exceeded the total time budget")
        if len(payload) > max_bytes:
            raise SourceTooLargeError(f"source exceeds byte limit ({max_bytes} bytes)")
        return payload.decode("utf-8", errors="replace"), source_url, 200
    request = Request(source_url, headers={"User-Agent": "codex-obsidian-skills/1.0"})
    deadline = time.monotonic() + total_timeout
    with urlopen(request, timeout=min(timeout, total_timeout)) as response:
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                declared_length = int(content_length)
            except ValueError:
                declared_length = None
            if declared_length is not None and declared_length > max_bytes:
                raise SourceTooLargeError(f"source Content-Length exceeds byte limit ({max_bytes} bytes)")
        content_type = response.headers.get("content-type", "")
        charset_match = re.search(r"charset=([^;\s]+)", content_type)
        encoding = charset_match.group(1).strip("\"'") if charset_match else "utf-8"
        final_url = normalize_url(response.geturl() or source_url)
        payload = _read_limited(response, max_bytes=max_bytes, deadline=deadline)
        return payload.decode(encoding, errors="replace"), final_url, response.getcode()


def read_source(
    source_url: str,
    timeout: float = 15.0,
    *,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    total_timeout: float = DEFAULT_TOTAL_TIMEOUT_SECONDS,
) -> str:
    return read_source_with_metadata(
        source_url,
        timeout=timeout,
        max_bytes=max_bytes,
        total_timeout=total_timeout,
    )[0]


def error_summary(exc: BaseException) -> str:
    text = normalize_space(str(exc))
    if not text:
        text = exc.__class__.__name__
    return text[:240]


def classify_url(url: str, label: str = "") -> str:
    parsed = urlparse(url)
    path = parsed.path.lower()
    text = f"{url} {label}".lower()

    if path.endswith(TRANSCRIPT_EXTENSIONS) or "transcript" in text or "caption" in text:
        return "transcript"
    if path.endswith(SLIDE_EXTENSIONS) or "slide" in text or "ppt" in text:
        return "slides"
    if path.endswith(BOOK_EXTENSIONS):
        return "book"
    if path.endswith(PDF_EXTENSIONS):
        if BOOK_PATH_RE.search(path) or "book" in text or "chapter" in text:
            return "book_pdf"
        return "pdf"
    if VIDEO_HOST_RE.search(parsed.netloc) or VIDEO_PATH_RE.search(path) or "video" in text or "lecture" in text:
        return "video"
    if BOOK_PATH_RE.search(path) or "book" in text or "chapter" in text or "reading" in text:
        return "book_or_chapter"
    if COURSE_PATH_RE.search(path) or "course" in text or "syllabus" in text:
        return "course_page"
    return "web_page"


def is_provenance_helper_link(url: str, label: str = "", kind: str | None = None) -> bool:
    """Return whether a link is structurally collection provenance, not study material.

    Keep ambiguous links as learning resources.  Only explicit static-bundle
    shapes, API shapes paired with helper labels, and unambiguous navigation
    labels become helpers.  Direct PDFs, slides, transcripts, and books remain
    learning resources even when served below an API-like path.
    """

    effective_kind = kind or classify_url(url, label)
    if effective_kind in DIRECT_RESOURCE_KINDS:
        return False
    parsed = urlparse(url)
    path = unquote(parsed.path).casefold()
    normalized_label = normalize_space(label)
    if path.endswith(STATIC_HELPER_EXTENSIONS):
        basename = Path(path).name
        if STATIC_HELPER_LABEL_RE.search(normalized_label):
            return True
        if normalized_label.casefold() in {"", basename} and STATIC_HELPER_BASENAME_RE.fullmatch(
            basename
        ):
            return True
    if is_api_shaped_url(url) and API_HELPER_LABEL_RE.search(normalize_space(label)):
        return True
    return effective_kind == "web_page" and normalized_label.casefold() in NAVIGATION_HELPER_LABELS


def is_api_shaped_url(url: str) -> bool:
    parsed = urlparse(url)
    path = unquote(parsed.path).casefold()
    hostname = (parsed.hostname or "").casefold()
    return bool(
        API_HELPER_PATH_RE.search(path)
        or hostname.startswith("api.")
        or ".api." in hostname
    )


def collect_page(
    source: str,
    timeout: float = 15.0,
    *,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    total_timeout: float = DEFAULT_TOTAL_TIMEOUT_SECONDS,
) -> PageRecord:
    source_url = source_to_url(source)
    source_kind = classify_url(source_url)
    if source_kind in DIRECT_RESOURCE_KINDS:
        parsed_source = urlparse(source_url)
        if parsed_source.scheme == "file":
            try:
                ensure_safe_input_file(Path(url2pathname(parsed_source.path)))
            except (OSError, ValueError) as exc:
                raise LocalSourceAccessError(str(exc)) from exc
        return PageRecord(
            original_source=source,
            canonical_url=source_url,
            title=title_from_url(source_url),
            kind=source_kind,
            access_status="recorded",
            description=f"Direct {source_kind.replace('_', ' ')} resource collected from the input URL.",
            error="",
            links=(),
            final_url=source_url,
            access_class="recorded",
        )

    text, final_url, http_status = read_source_with_metadata(
        source_url,
        timeout=timeout,
        max_bytes=max_bytes,
        total_timeout=total_timeout,
    )
    parser = LearningHTMLParser()
    parser.feed(text)

    page_url = normalize_url(urljoin(final_url, parser.canonical)) if parser.canonical else final_url
    title = parser.title or Path(urlparse(page_url).path).name or page_url
    page_kind = classify_url(page_url, title)
    login_required = bool(LOGIN_PAGE_RE.search(text[:20000])) and (
        "password" in text[:20000].lower() or any(marker in title.lower() for marker in ("login", "sign in", "log in"))
    )
    links = []
    for href, label in parser.links:
        raw_href = href.strip()
        if not raw_href or raw_href.startswith("#"):
            continue
        joined = urljoin(page_url, raw_href)
        parsed_link = urlparse(joined)
        if parsed_link.scheme.casefold() not in {"http", "https", "file"}:
            continue
        defragmented, fragment = urldefrag(joined)
        page_without_fragment, _page_fragment = urldefrag(page_url)
        if fragment and normalize_url(defragmented) == normalize_url(page_without_fragment):
            continue
        absolute = normalize_url(joined)
        kind = classify_url(absolute, label)
        provenance_only = is_provenance_helper_link(absolute, label, kind)
        if (
            kind == "web_page"
            and not label
            and not provenance_only
            and not is_api_shaped_url(absolute)
        ):
            continue
        links.append(
            LinkRecord(
                source=page_url,
                title=label or absolute,
                url=absolute,
                kind=kind,
                provenance_only=provenance_only,
            )
        )

    return PageRecord(
        original_source=source,
        canonical_url=page_url,
        title=title,
        kind=page_kind,
        access_status="login_required" if login_required else "ok",
        description=parser.description,
        error="",
        links=tuple(dedupe_links(links)),
        final_url=final_url,
        http_status=http_status,
        access_class="login_required" if login_required else "ok",
    )


def collect_source(
    source: str,
    timeout: float = 15.0,
    *,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    total_timeout: float = DEFAULT_TOTAL_TIMEOUT_SECONDS,
) -> PageRecord:
    try:
        return collect_page(source, timeout=timeout, max_bytes=max_bytes, total_timeout=total_timeout)
    except Exception as exc:
        try:
            source_url = source_to_url(source)
        except Exception:
            source_url = source
        source_kind = classify_url(source_url)
        if isinstance(exc, HTTPError):
            http_status = exc.code
            access_status = f"http_{http_status}"
            access_class = "http_error"
            description = f"HTTP request returned status {http_status}; kept for manifest coverage."
            final_url = normalize_url(exc.geturl() or source_url)
        elif isinstance(exc, SourceTooLargeError):
            http_status = None
            access_status = "too_large"
            access_class = "size_limit"
            description = "Source exceeded the configured byte budget; kept for manifest coverage."
            final_url = source_url
        elif isinstance(exc, (TimeoutError, socket.timeout)):
            http_status = None
            access_status = "timeout"
            access_class = "timeout"
            description = "Source request timed out; kept for manifest coverage."
            final_url = source_url
        elif isinstance(exc, URLError):
            http_status = None
            access_status = "network_error"
            access_class = "network_error"
            description = "Source could not be reached; kept for manifest coverage."
            final_url = source_url
        elif isinstance(exc, (FileNotFoundError, IsADirectoryError, LocalSourceAccessError)):
            http_status = None
            access_status = "inaccessible"
            access_class = "filesystem_error"
            description = "Source could not be read; kept for manifest coverage."
            final_url = source_url
        else:
            http_status = None
            access_status = "parse_error"
            access_class = "parse_error"
            description = "Source could not be parsed; kept for manifest coverage."
            final_url = source_url
        return PageRecord(
            original_source=source,
            canonical_url=source_url,
            title=title_from_url(source_url),
            kind=source_kind,
            access_status=access_status,
            description=description,
            error=error_summary(exc),
            links=(),
            final_url=final_url,
            http_status=http_status,
            access_class=access_class,
        )


def dedupe_links(links: Iterable[LinkRecord]) -> list[LinkRecord]:
    seen: set[tuple[str, str]] = set()
    positions: dict[tuple[str, str], int] = {}
    result: list[LinkRecord] = []
    for link in links:
        key = (link.url, link.kind)
        if key in seen:
            existing_index = positions[key]
            if result[existing_index].provenance_only and not link.provenance_only:
                result[existing_index] = link
            continue
        seen.add(key)
        positions[key] = len(result)
        result.append(link)
    return result


def collect_sources(
    sources: list[str],
    timeout: float = 15.0,
    *,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    total_timeout: float = DEFAULT_TOTAL_TIMEOUT_SECONDS,
) -> list[PageRecord]:
    return [
        collect_source(source, timeout=timeout, max_bytes=max_bytes, total_timeout=total_timeout)
        for source in sources
    ]


def markdown_escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def build_manifest(pages: list[PageRecord]) -> str:
    lines = [
        "# Source Manifest",
        "",
        "## Pages",
        "",
        "| Kind | Title | Original Source | URL | Access | Status | Error | Description |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for page in pages:
        status = "ok" if page.access_status == "ok" else page.access_status.replace("_", " ")
        lines.append(
            f"| {page.kind} | {markdown_escape_cell(page.title)} | {markdown_escape_cell(page.original_source)} | "
            f"{markdown_escape_cell(page.canonical_url)} | {page.access_status} | {status} | "
            f"{markdown_escape_cell(page.error)} | {markdown_escape_cell(page.description)} |"
        )

    lines.extend(
        [
            "",
            "## Access Evidence",
            "",
            "| Original Source | Final URL | HTTP Status | Access Class |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for page in pages:
        lines.append(
            f"| {markdown_escape_cell(page.original_source)} | {markdown_escape_cell(page.final_url or page.canonical_url)} | "
            f"{page.http_status if page.http_status is not None else ''} | {page.access_class} |"
        )

    lines.extend(
        [
            "",
            "## Learning Resources",
            "",
            "| Kind | Title | URL | Access | Status | Error | Source Page |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    for page in pages:
        if page.kind in DIRECT_RESOURCE_KINDS:
            status = "ok" if page.access_status == "ok" else page.access_status.replace("_", " ")
            lines.append(
                f"| {page.kind} | {markdown_escape_cell(page.title)} | {markdown_escape_cell(page.url)} | "
                f"{page.access_status} | {status} | {markdown_escape_cell(page.error)} | {markdown_escape_cell(page.url)} |"
            )
        for link in page.links:
            if link.provenance_only:
                continue
            lines.append(
                f"| {link.kind} | {markdown_escape_cell(link.title)} | {markdown_escape_cell(link.url)} | "
                f"listed | listed |  | {markdown_escape_cell(link.source)} |"
            )

    lines.extend(
        [
            "",
            "## Provenance Helpers",
            "",
            "| Kind | Title | URL | Source Page |",
            "| --- | --- | --- | --- |",
        ]
    )
    for page in pages:
        for link in page.links:
            if not link.provenance_only:
                continue
            lines.append(
                f"| {link.kind} | {markdown_escape_cell(link.title)} | {markdown_escape_cell(link.url)} | "
                f"{markdown_escape_cell(link.source)} |"
            )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Verify access rights before downloading or quoting source material.",
            "- Use videos, slides, transcripts, and chapters as sources for rewritten study notes, not copied page dumps.",
            "- For local PPT/PPTX/PDF extraction, use $ppt-to-md-for-obsidian.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    configure_output_encoding()
    parser = argparse.ArgumentParser(description="Collect web learning sources into a Markdown manifest.")
    parser.add_argument("sources", nargs="+", help="URL or local HTML file")
    parser.add_argument("--out", type=Path, help="Output Markdown path. Defaults to stdout.")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_RESPONSE_BYTES,
        help=f"Maximum bytes per source (default: {DEFAULT_MAX_RESPONSE_BYTES})",
    )
    parser.add_argument(
        "--total-timeout",
        type=float,
        default=DEFAULT_TOTAL_TIMEOUT_SECONDS,
        help=f"Total read budget per source in seconds (default: {DEFAULT_TOTAL_TIMEOUT_SECONDS:g})",
    )
    args = parser.parse_args()

    pages = collect_sources(
        args.sources,
        timeout=args.timeout,
        max_bytes=args.max_bytes,
        total_timeout=args.total_timeout,
    )
    manifest = build_manifest(pages)
    if args.out:
        try:
            safe_write_text(args.out, manifest)
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(args.out)
    else:
        print(manifest, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
