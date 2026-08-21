#!/usr/bin/env python3
"""Audit external URLs referenced by a vault without writing into the vault.

The online mode is deliberately separate from the deterministic local gate.
It uses a small JSON cache under /tmp by default, follows normal redirects,
and distinguishes access restrictions from confirmed missing resources.  Unit
tests inject a fake opener; CI never needs the public Internet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from notes_utils import remove_fenced_code

URL_RE = re.compile(r"https?://[^\s<>'\"\]\[|]+", re.I)
NON_URL_PROSE_RE = re.compile(r"[\u3400-\u9fff]")
URL_PROSE_TERMINATOR_RE = re.compile(r"[)\]}>）】》」』：；，。！？、]")
TRAILING_PUNCTUATION = ",.;:!?，。；：！？、)（）】》」』\"'`"
DEFAULT_CACHE_DIR = Path("/tmp/solvenotes-web-cache")
STATUSES = (
    "OK",
    "REDIRECT",
    "STALE_VERSION",
    "AUTH_REQUIRED",
    "PAYWALL",
    "ROBOTS_BLOCKED",
    "RATE_LIMITED",
    "TEMPORARY_FAILURE",
    "NOT_FOUND",
    "DOMAIN_GONE",
    "MANUAL_REVIEW",
)


def normalize_url(value: str) -> str:
    value = value.strip().rstrip(TRAILING_PUNCTUATION)
    parts = urlsplit(value)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ""))


def request_url(value: str) -> str:
    """Encode Unicode paths and IDNs before handing a URL to urllib."""

    parts = urlsplit(value)
    hostname = parts.hostname or ""
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        hostname = parts.netloc
    netloc = hostname
    if parts.port is not None:
        netloc = f"{netloc}:{parts.port}"
    safe_path = quote(parts.path, safe="/%:@!$&'()*+,;=-._~")
    safe_query = quote(parts.query, safe="!$&'()*+,;=:/?@%_-.")
    return urlunsplit((parts.scheme, netloc, safe_path, safe_query, ""))


def markdown_paths(root: Path, *, changed_only: bool = False) -> list[Path]:
    ignored = {".git", ".obsidian", "__pycache__", ".pytest_cache", ".ruff_cache"}
    if not changed_only:
        return sorted(
            path
            for path in root.rglob("*.md")
            if path.is_file() and not any(part in ignored for part in path.parts)
        )
    try:
        changed = subprocess.run(
            ["git", "-C", str(root), "diff", "--name-only", "HEAD", "--", "*.md"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.splitlines()
        untracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard", "--", "*.md"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.splitlines()
    except (OSError, subprocess.TimeoutExpired):
        return []
    paths: list[Path] = []
    for name in sorted(set(changed + untracked)):
        candidate = root / name
        if candidate.is_file() and not any(part in ignored for part in candidate.parts):
            paths.append(candidate)
    return paths


def extract_urls(text: str) -> set[str]:
    urls: set[str] = set()
    for match in URL_RE.finditer(text):
        candidate = match.group(0)
        prose_start = NON_URL_PROSE_RE.search(candidate)
        if prose_start:
            candidate = candidate[: prose_start.start()]
        prose_separator = URL_PROSE_TERMINATOR_RE.search(candidate)
        if prose_separator:
            candidate = candidate[: prose_separator.start()]
        normalized = normalize_url(candidate)
        if urlsplit(normalized).netloc:
            urls.add(normalized)
    return urls


def strip_fenced_code(text: str) -> str:
    """Exclude executable/code examples; they are not source citations."""

    return remove_fenced_code(text)


def url_sources(root: Path, *, changed_only: bool = False) -> dict[str, list[str]]:
    sources: dict[str, list[str]] = {}
    for path in markdown_paths(root, changed_only=changed_only):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            urls = extract_urls(strip_fenced_code(text))
        except OSError:
            continue
        relative = path.relative_to(root).as_posix()
        for url in urls:
            sources.setdefault(url, []).append(relative)
    return {url: sorted(paths) for url, paths in sorted(sources.items())}


def cache_path(cache_dir: Path, url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.json"


def classify_http(code: int, *, final_url: str, original_url: str, headers: dict[str, str] | None = None) -> str:
    headers = {key.lower(): value for key, value in (headers or {}).items()}
    if 200 <= code < 300:
        return "REDIRECT" if normalize_url(final_url) != normalize_url(original_url) else "OK"
    if code in {301, 302, 303, 307, 308}:
        return "REDIRECT"
    if code in {401}:
        return "AUTH_REQUIRED"
    if code in {402}:
        return "PAYWALL"
    if code in {403}:
        if "robot" in headers.get("server", "").lower() or "robot" in headers.get("x-robots-tag", "").lower():
            return "ROBOTS_BLOCKED"
        return "MANUAL_REVIEW"
    if code == 429:
        return "RATE_LIMITED"
    if code in {404}:
        return "NOT_FOUND"
    if code in {410}:
        return "DOMAIN_GONE"
    if 500 <= code < 600:
        return "TEMPORARY_FAILURE"
    return "MANUAL_REVIEW"


@dataclass
class Result:
    url: str
    sources: list[str]
    status: str
    http_status: int | None = None
    final_url: str | None = None
    content_type: str | None = None
    error: str | None = None
    checked_at: str | None = None
    cached: bool = False

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _response_headers(response: Any) -> dict[str, str]:
    headers = getattr(response, "headers", {})
    if hasattr(headers, "items"):
        return {str(key): str(value) for key, value in headers.items()}
    return {}


def check_url(
    url: str,
    *,
    cache_dir: Path,
    timeout: float,
    offline_cache_only: bool = False,
    interval: float = 0.1,
    opener: Callable[..., Any] = urlopen,
) -> Result:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path(cache_dir, url)
    if path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            return Result(**{**cached, "cached": True})
        except (OSError, TypeError, ValueError):
            pass
    checked_at = datetime.now(timezone.utc).isoformat()
    if offline_cache_only:
        result = Result(url=url, sources=[], status="MANUAL_REVIEW", error="cache_missing", checked_at=checked_at)
        return result

    try:
        encoded_url = request_url(url)
    except ValueError as exc:
        result = Result(url=url, sources=[], status="MANUAL_REVIEW", error=f"invalid_url: {exc}", checked_at=checked_at)
        path.write_text(json.dumps(result.to_json(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result

    request = Request(
        encoded_url,
        headers={
            "User-Agent": "SolvenotesExternalSourceAudit/1.0 (+read-only; contact unavailable)",
            "Accept": "text/html,application/pdf,text/plain;q=0.8,*/*;q=0.1",
        },
        method="HEAD",
    )
    try:
        with opener(request, timeout=timeout) as response:
            headers = _response_headers(response)
            final_url = getattr(response, "geturl", lambda: url)()
            code = int(getattr(response, "status", getattr(response, "code", 200)))
            result = Result(
                url=url,
                sources=[],
                status=classify_http(code, final_url=final_url, original_url=url, headers=headers),
                http_status=code,
                final_url=final_url,
                content_type=headers.get("Content-Type") or headers.get("content-type"),
                checked_at=checked_at,
            )
    except HTTPError as exc:
        headers = _response_headers(exc)
        result = Result(
            url=url,
            sources=[],
            status=classify_http(exc.code, final_url=getattr(exc, "url", url), original_url=url, headers=headers),
            http_status=exc.code,
            final_url=getattr(exc, "url", url),
            error=str(exc),
            checked_at=checked_at,
        )
    except (TimeoutError, URLError, OSError) as exc:
        result = Result(url=url, sources=[], status="TEMPORARY_FAILURE", error=str(exc), checked_at=checked_at)

    payload = result.to_json()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def scan(
    root: Path,
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    max_urls: int | None = None,
    domain: str | None = None,
    timeout: float = 10.0,
    total_timeout: float | None = 300.0,
    changed_only: bool = False,
    offline_cache_only: bool = False,
    interval: float = 0.1,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    root = root.expanduser().absolute()
    sources = url_sources(root, changed_only=changed_only)
    urls = list(sources)
    if domain:
        domain_lower = domain.casefold()
        urls = [url for url in urls if domain_lower in urlsplit(url).netloc.casefold()]
    if max_urls is not None:
        urls = urls[: max(0, max_urls)]
    results: list[Result] = []
    started = time.monotonic()
    stopped_due_to_total_timeout = False
    for index, url in enumerate(urls):
        if total_timeout is not None and time.monotonic() - started >= max(0.0, total_timeout):
            stopped_due_to_total_timeout = True
            break
        if index and interval > 0 and not offline_cache_only:
            time.sleep(interval)
        result = check_url(
            url,
            cache_dir=cache_dir,
            timeout=timeout,
            offline_cache_only=offline_cache_only,
            opener=opener,
        )
        result.sources = sources[url]
        results.append(result)
    counts = {status: 0 for status in STATUSES}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return {
        "root": str(root),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "changed_only": changed_only,
        "offline_cache_only": offline_cache_only,
        "url_count": len(results),
        "requested_url_count": len(urls),
        "stopped_due_to_total_timeout": stopped_due_to_total_timeout,
        "status_counts": counts,
        "results": [result.to_json() for result in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--changed-only", action="store_true")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--max-urls", type=int)
    parser.add_argument("--domain")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--total-timeout", type=float, default=300.0)
    parser.add_argument("--interval", type=float, default=0.1)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--offline-cache-only", action="store_true")
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error(f"root is not a directory: {args.root}")
    payload = scan(
        args.root,
        cache_dir=args.cache_dir,
        max_urls=args.max_urls,
        domain=args.domain,
        timeout=args.timeout,
        total_timeout=args.total_timeout,
        changed_only=args.changed_only,
        offline_cache_only=args.offline_cache_only,
        interval=args.interval,
    )
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"external_urls {payload['url_count']}")
    for status in STATUSES:
        print(f"external_{status.lower()} {payload['status_counts'].get(status, 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
