from __future__ import annotations

from pathlib import Path
import sys
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import collect_web_sources  # noqa: E402
from scripts.collect_web_sources import (  # noqa: E402
    build_manifest,
    classify_url,
    collect_page,
    collect_sources,
    normalize_url,
)


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
    assert page.original_source == str(fixture)
    assert page.canonical_url == "https://example.edu/ml-mini-course/"
    assert page.access_status == "ok"
    assert page.error == ""
    assert page.title == "Machine Learning Mini Course"
    assert page.kind == "course_page"
    assert page.description.startswith("A small course index")

    kinds = {link.kind for link in page.links}
    assert {"video", "slides", "transcript", "book_or_chapter"}.issubset(kinds)

    manifest = build_manifest(pages)
    assert "# Source Manifest" in manifest
    assert "| Kind | Title | Original Source | URL | Access | Status | Error | Description |" in manifest
    assert "| Kind | Title | URL | Access | Status | Error | Source Page |" in manifest
    assert "| course_page | Machine Learning Mini Course |" in manifest
    assert "Lecture 01 Video" in manifest
    assert "Lecture 01 Slides" in manifest
    assert "Book Chapter 02" in manifest


def test_collect_sources_accepts_direct_pdf_url_without_reading_binary(monkeypatch):
    def fail_read(source_url: str, timeout: float = 15.0) -> str:
        raise AssertionError("direct PDF URL should not be parsed as HTML")

    monkeypatch.setattr(collect_web_sources, "read_source", fail_read)

    pages = collect_sources(["https://example.com/papers/Zhu_From_Noise_Modeling_CVPR_2016_paper.pdf"])

    assert len(pages) == 1
    page = pages[0]
    assert page.kind == "pdf"
    assert page.access_status == "recorded"
    assert page.error == ""
    assert page.title == "Zhu From Noise Modeling CVPR 2016 paper"

    manifest = build_manifest(pages)
    assert "| pdf | Zhu From Noise Modeling CVPR 2016 paper | https://example.com/papers/Zhu_From_Noise_Modeling_CVPR_2016_paper.pdf |" in manifest
    assert "| pdf | Zhu From Noise Modeling CVPR 2016 paper | https://example.com/papers/Zhu_From_Noise_Modeling_CVPR_2016_paper.pdf | recorded | recorded |  | https://example.com/papers/Zhu_From_Noise_Modeling_CVPR_2016_paper.pdf |" in manifest


def test_collect_sources_preserves_inaccessible_source_in_manifest(tmp_path: Path):
    missing = tmp_path / "missing-course.html"

    pages = collect_sources([str(missing)])

    assert len(pages) == 1
    page = pages[0]
    assert page.original_source == str(missing)
    assert page.kind == "course_page"
    assert page.access_status == "inaccessible"
    assert page.error
    assert page.links == ()

    manifest = build_manifest(pages)
    assert "inaccessible" in manifest
    assert "missing-course.html" in manifest
    assert "Source could not be read" in manifest


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


def test_collect_page_records_final_url_and_login_required_state(monkeypatch):
    monkeypatch.setattr(
        collect_web_sources,
        "read_source_with_metadata",
        lambda source_url, timeout=15.0: (
            "<title>Login</title><form><input type='password'></form>",
            "https://example.com/final-login",
            200,
        ),
    )

    page = collect_page("https://example.com/start")

    assert page.final_url == "https://example.com/final-login"
    assert page.http_status == 200
    assert page.access_status == "login_required"
    assert page.access_class == "login_required"
    assert "final-login" in build_manifest([page])


def test_collect_source_classifies_http_errors_without_collapsing_to_inaccessible(monkeypatch):
    def raise_404(source_url: str, timeout: float = 15.0):
        raise HTTPError(source_url, 404, "Not Found", hdrs=None, fp=None)

    monkeypatch.setattr(collect_web_sources, "collect_page", raise_404)

    page = collect_web_sources.collect_source("https://example.com/missing-course")

    assert page.access_status == "http_404"
    assert page.access_class == "http_error"
    assert page.http_status == 404
    assert page.error


def test_normalize_url_preserves_windows_file_drive_colon():
    assert normalize_url("file:///C:/Users/Test/course index.html") == "file:///C:/Users/Test/course%20index.html"
