#!/usr/bin/env python3
"""Collect a Markdown source manifest from course, slide, and book web pages."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
from typing import Iterable
from urllib.parse import quote, unquote, urljoin, urlparse, urlsplit, urlunsplit
from urllib.request import Request, url2pathname, urlopen


VIDEO_HOST_RE = re.compile(r"(youtube|youtu\.be|bilibili|vimeo|coursera|edx|khanacademy|ocw|mit\.edu)", re.I)
VIDEO_PATH_RE = re.compile(r"(/watch|/video|/lecture|/lesson|/play)", re.I)
SLIDE_EXTENSIONS = (".ppt", ".pptx", ".odp", ".key")
PDF_EXTENSIONS = (".pdf",)
BOOK_EXTENSIONS = (".epub", ".mobi")
TRANSCRIPT_EXTENSIONS = (".vtt", ".srt", ".ttml", ".txt")
BOOK_PATH_RE = re.compile(r"(/book|/books|/chapter|/chapters|/readings?|/textbook)", re.I)
COURSE_PATH_RE = re.compile(r"(/course|/courses|/class|/classes|/syllabus|/module|/modules)", re.I)
DIRECT_RESOURCE_KINDS = {"book", "book_pdf", "pdf", "slides", "transcript"}


@dataclass(frozen=True)
class LinkRecord:
    source: str
    title: str
    url: str
    kind: str


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
    return Path(source).expanduser().resolve().as_uri()


def title_from_url(url: str) -> str:
    parsed = urlparse(url)
    path_name = Path(unquote(parsed.path)).name
    if not path_name:
        return parsed.netloc or url
    stem = Path(path_name).stem
    return normalize_space(re.sub(r"[_-]+", " ", stem)) or path_name


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.scheme:
        return url
    path = quote(unquote(parts.path), safe="/:@")
    query = quote(unquote(parts.query), safe="=&?/:@+,%")
    fragment = quote(unquote(parts.fragment), safe="=&?/:@+,%")
    return urlunsplit((parts.scheme, parts.netloc, path, query, fragment))


def read_source(source_url: str, timeout: float = 15.0) -> str:
    parsed = urlparse(source_url)
    if parsed.scheme == "file":
        return Path(url2pathname(parsed.path)).read_text(encoding="utf-8", errors="replace")
    request = Request(source_url, headers={"User-Agent": "codex-obsidian-skills/1.0"})
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        charset_match = re.search(r"charset=([^;\s]+)", content_type)
        encoding = charset_match.group(1) if charset_match else "utf-8"
        return response.read().decode(encoding, errors="replace")


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


def collect_page(source: str, timeout: float = 15.0) -> PageRecord:
    source_url = source_to_url(source)
    source_kind = classify_url(source_url)
    if source_kind in DIRECT_RESOURCE_KINDS:
        return PageRecord(
            original_source=source,
            canonical_url=source_url,
            title=title_from_url(source_url),
            kind=source_kind,
            access_status="recorded",
            description=f"Direct {source_kind.replace('_', ' ')} resource collected from the input URL.",
            error="",
            links=(),
        )

    text = read_source(source_url, timeout=timeout)
    parser = LearningHTMLParser()
    parser.feed(text)

    page_url = normalize_url(urljoin(source_url, parser.canonical)) if parser.canonical else source_url
    title = parser.title or Path(urlparse(page_url).path).name or page_url
    page_kind = classify_url(page_url, title)
    links = []
    for href, label in parser.links:
        absolute = normalize_url(urljoin(page_url, href))
        kind = classify_url(absolute, label)
        if kind == "web_page" and not label:
            continue
        links.append(LinkRecord(source=page_url, title=label or absolute, url=absolute, kind=kind))

    return PageRecord(
        original_source=source,
        canonical_url=page_url,
        title=title,
        kind=page_kind,
        access_status="ok",
        description=parser.description,
        error="",
        links=tuple(dedupe_links(links)),
    )


def collect_source(source: str, timeout: float = 15.0) -> PageRecord:
    try:
        return collect_page(source, timeout=timeout)
    except Exception as exc:
        try:
            source_url = source_to_url(source)
        except Exception:
            source_url = source
        source_kind = classify_url(source_url)
        return PageRecord(
            original_source=source,
            canonical_url=source_url,
            title=title_from_url(source_url),
            kind=source_kind,
            access_status="inaccessible",
            description="Source could not be read; kept for manifest coverage.",
            error=error_summary(exc),
            links=(),
        )


def dedupe_links(links: Iterable[LinkRecord]) -> list[LinkRecord]:
    seen: set[tuple[str, str]] = set()
    result: list[LinkRecord] = []
    for link in links:
        key = (link.url, link.kind)
        if key in seen:
            continue
        seen.add(key)
        result.append(link)
    return result


def collect_sources(sources: list[str], timeout: float = 15.0) -> list[PageRecord]:
    return [collect_source(source, timeout=timeout) for source in sources]


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
            lines.append(
                f"| {link.kind} | {markdown_escape_cell(link.title)} | {markdown_escape_cell(link.url)} | "
                f"listed | listed |  | {markdown_escape_cell(link.source)} |"
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
    args = parser.parse_args()

    pages = collect_sources(args.sources, timeout=args.timeout)
    manifest = build_manifest(pages)
    if args.out:
        args.out.write_text(manifest, encoding="utf-8")
        print(args.out)
    else:
        print(manifest, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
