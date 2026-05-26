from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.collect_web_sources import build_manifest, classify_url, collect_sources, collect_page, normalize_url


def test_classify_url_detects_learning_resource_types():
    assert classify_url("https://example.com/watch/lecture-01") == "video"
    assert classify_url("https://example.com/slides/week1.pptx") == "slides"
    assert classify_url("https://example.com/readings/book.pdf", "book pdf") == "book_pdf"
    assert classify_url("https://example.com/captions/lecture.vtt") == "transcript"
    assert classify_url("https://example.com/book/chapter-1") == "book_or_chapter"


def test_collect_sources_from_local_html_fixture():
    fixture = ROOT / "examples" / "sample-web-course" / "index.html"
    pages = collect_sources([str(fixture)])

    assert len(pages) == 1
    page = pages[0]
    assert page.title == "Machine Learning Mini Course"
    assert page.kind == "course_page"
    assert page.description.startswith("A small course index")

    kinds = {link.kind for link in page.links}
    assert {"video", "slides", "transcript", "book_or_chapter"}.issubset(kinds)

    manifest = build_manifest(pages)
    assert "# Source Manifest" in manifest
    assert "Lecture 01 Video" in manifest
    assert "Lecture 01 Slides" in manifest
    assert "Book Chapter 02" in manifest


def test_collect_sources_accepts_direct_pdf_url_without_reading_binary():
    pages = collect_sources(["https://example.com/papers/Zhu_From_Noise_Modeling_CVPR_2016_paper.pdf"])

    assert len(pages) == 1
    page = pages[0]
    assert page.kind == "pdf"
    assert page.title == "Zhu From Noise Modeling CVPR 2016 paper"

    manifest = build_manifest(pages)
    assert "| pdf | Zhu From Noise Modeling CVPR 2016 paper |" in manifest


def test_collect_page_accepts_file_uri_with_spaces(tmp_path: Path):
    html_path = tmp_path / "course index.html"
    html_path.write_text(
        "<!doctype html><title>Course With Spaces</title><a href='week 1.pptx'>Week 1</a>",
        encoding="utf-8",
    )

    page = collect_page(html_path.as_uri())

    assert page.title == "Course With Spaces"
    assert page.links[0].kind == "slides"
    assert "week%201.pptx" in page.links[0].url


def test_normalize_url_preserves_windows_file_drive_colon():
    assert normalize_url("file:///C:/Users/Test/course index.html") == "file:///C:/Users/Test/course%20index.html"
