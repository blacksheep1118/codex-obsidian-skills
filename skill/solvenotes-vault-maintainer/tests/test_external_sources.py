from __future__ import annotations

from pathlib import Path

import check_external_sources as audit


class FakeResponse:
    status = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __init__(self, url: str) -> None:
        self._url = url

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args) -> None:
        return None

    def geturl(self) -> str:
        return self._url


def test_extract_urls_normalizes_fragments_and_markdown_punctuation() -> None:
    urls = audit.extract_urls(
        "[官方](https://example.com/docs#section), https://example.com/docs#other。"
    )

    assert urls == {"https://example.com/docs"}


def test_extract_urls_stops_before_chinese_prose_after_a_link() -> None:
    urls = audit.extract_urls("教材见 https://example.com/book.html)，第 1 章继续。")

    assert urls == {"https://example.com/book.html"}


def test_extract_urls_stops_before_non_chinese_parenthetical_prose() -> None:
    urls = audit.extract_urls("ELBO 见 https://arxiv.org/abs/1601.00670)：ELBO、mean-field。")

    assert urls == {"https://arxiv.org/abs/1601.00670"}


def test_url_sources_ignores_code_examples(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text(
        "正文见 https://example.com/docs。\n\n```bash\ncurl http://host:port/health\n```\n",
        encoding="utf-8",
    )

    assert audit.url_sources(root) == {"https://example.com/docs": ["note.md"]}


def test_url_sources_ignores_tilde_and_long_backtick_fences(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text(
        "正文见 https://example.com/docs。\n"
        "~~~text\nhttps://tilde.invalid\n~~~\n"
        "````text\n```\nhttps://still-fenced.invalid\n````\n",
        encoding="utf-8",
    )

    assert audit.url_sources(root) == {"https://example.com/docs": ["note.md"]}


def test_request_url_percent_encodes_unicode_paths() -> None:
    assert audit.request_url("https://example.com/课程/机器学习") == (
        "https://example.com/%E8%AF%BE%E7%A8%8B/%E6%9C%BA%E5%99%A8%E5%AD%A6%E4%B9%A0"
    )


def test_scan_uses_mock_opener_and_records_sources(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("参见 https://example.com/docs。\n", encoding="utf-8")

    def opener(request, timeout):
        assert request.full_url == "https://example.com/docs"
        assert timeout == 3.0
        return FakeResponse(request.full_url)

    payload = audit.scan(root, cache_dir=tmp_path / "cache", timeout=3.0, opener=opener)

    assert payload["url_count"] == 1
    assert payload["status_counts"]["OK"] == 1
    assert payload["results"][0]["sources"] == ["note.md"]


def test_cache_and_offline_cache_only_do_not_call_network_twice(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "note.md").write_text("https://example.com/docs\n", encoding="utf-8")
    cache = tmp_path / "cache"
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        return FakeResponse(request.full_url)

    audit.scan(root, cache_dir=cache, opener=opener)
    cached = audit.scan(root, cache_dir=cache, offline_cache_only=True, opener=lambda *_args: 1)

    assert calls == 1
    assert cached["status_counts"]["OK"] == 1
    assert cached["results"][0]["cached"] is True


def test_http_statuses_are_not_collapsed_into_dead_link() -> None:
    assert audit.classify_http(403, final_url="https://x.test", original_url="https://x.test") == "MANUAL_REVIEW"
    assert audit.classify_http(429, final_url="https://x.test", original_url="https://x.test") == "RATE_LIMITED"
    assert audit.classify_http(410, final_url="https://x.test", original_url="https://x.test") == "DOMAIN_GONE"
    assert audit.classify_http(200, final_url="https://x.test/new", original_url="https://x.test") == "REDIRECT"
