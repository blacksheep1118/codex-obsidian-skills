#!/usr/bin/env python3
"""RFC 3986-aware URL identity helpers shared by web-note tools."""

from __future__ import annotations

import re
from urllib.parse import quote, urlsplit, urlunsplit


UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
PERCENT_ESCAPE_RE = re.compile(r"%([0-9A-Fa-f]{2})")
URL_TOKEN_RE = re.compile(r"(?:https?|file)://[^\s<>\"']+", re.I)


def _normalize_percent_escapes(value: str, *, safe: str) -> str:
    """Decode only unreserved octets and uppercase all other escapes."""

    def replace(match: re.Match[str]) -> str:
        byte = int(match.group(1), 16)
        character = chr(byte)
        return character if character in UNRESERVED else f"%{byte:02X}"

    normalized = PERCENT_ESCAPE_RE.sub(replace, value)
    return quote(normalized, safe=f"{safe}%")


def _normalize_netloc(value: str) -> str:
    userinfo, separator, host_port = value.rpartition("@")
    if not separator:
        userinfo = ""
        host_port = value
    if host_port.startswith("["):
        close = host_port.find("]")
        host = host_port[: close + 1] if close >= 0 else host_port
        port = host_port[close + 1 :] if close >= 0 else ""
    else:
        host, colon, port_value = host_port.partition(":")
        port = f":{port_value}" if colon else ""
    authority = f"{host.lower()}{port}"
    return f"{userinfo}@{authority}" if separator else authority


def normalize_url(value: str) -> str:
    """Return a stable URL identity without decoding reserved octets.

    Percent-encoded reserved characters such as ``%2F``, ``%26``, and ``%3D``
    remain encoded because decoding them can change path or query structure.
    """

    stripped = value.strip()
    parts = urlsplit(stripped)
    if not parts.scheme:
        return stripped
    scheme = parts.scheme.lower()
    netloc = _normalize_netloc(parts.netloc)
    path = _normalize_percent_escapes(parts.path, safe="/:@!$&'()*+,;=-._~")
    query = _normalize_percent_escapes(parts.query, safe="/?:@!$&'()*+,;=-._~")
    fragment = _normalize_percent_escapes(parts.fragment, safe="/?:@!$&'()*+,;=-._~")
    return urlunsplit((scheme, netloc, path, query, fragment))


def _trim_url_token(token: str) -> str:
    token = token.rstrip(".,;!?|`")
    for opening, closing in (("(", ")"), ("[", "]"), ("{", "}")):
        while token.endswith(closing) and token.count(closing) > token.count(opening):
            token = token[:-1]
    return token


def extract_url_identities(text: str) -> set[str]:
    """Extract URL tokens from prose and normalize each for exact comparison."""

    return {
        normalize_url(token)
        for match in URL_TOKEN_RE.finditer(text)
        if (token := _trim_url_token(match.group(0)))
    }
