#!/usr/bin/env python3
"""Scan repository text files for public-sharing privacy risks."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from notes_utils import ROOT, is_regular_file_without_symlinks, read_text

FORBIDDEN_ATTACHMENT_SUFFIXES = {
    ".7z",
    ".bin",
    ".ckpt",
    ".dmg",
    ".doc",
    ".docx",
    ".onnx",
    ".pdf",
    ".ppt",
    ".pptx",
    ".pth",
    ".pt",
    ".rar",
    ".safetensors",
    ".tar",
    ".tar.gz",
    ".zip",
}
IMAGE_MEDIA_SUFFIXES = {".gif", ".jpeg", ".jpg", ".png", ".webp"}

ABSOLUTE_PATH_PATTERNS = [
    re.compile(r"/" + r"Users/" + r"[^`\s)>\]]+"),
    re.compile(r"/" + r"home/" + r"[^`\s)>\]]+"),
    re.compile(r"/" + r"mnt/data" + r"[^`\s)>\]]*"),
    re.compile(r"C:" + r"\\Users\\" + r"[^`\s)>\]]+"),
]
SECRET_PATTERNS = [
    ("github_pat", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("github_token", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY")),
]
STRICT_FAILURE_CATEGORIES = {
    "absolute_path",
    "forbidden_attachment",
    *{label for label, _ in SECRET_PATTERNS},
}
EXAMPLE_PASSWORD_RE = re.compile(
    r"(?i)\b(?:password|passwd|pwd)\s*=\s*['\"]?(?:123456|password|admin|test)['\"]?"
)
HTTP_URL_RE = re.compile(r"https?://[^\s<>)\]]+")


def git_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        timeout=30,
    )
    if result.returncode:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"git ls-files failed: {stderr.strip()}")
    return [item.decode("utf-8", errors="surrogateescape") for item in result.stdout.split(b"\0") if item]


def matching_suffix(path: Path, suffixes: set[str]) -> str | None:
    """Return the longest complete filename suffix, case-insensitively."""

    lowercase_name = path.name.lower()
    return next(
        (suffix for suffix in sorted(suffixes, key=len, reverse=True) if lowercase_name.endswith(suffix)),
        None,
    )


def is_scannable(path: Path) -> bool:
    if matching_suffix(path, FORBIDDEN_ATTACHMENT_SUFFIXES | IMAGE_MEDIA_SUFFIXES):
        return False
    if path.name == "check_public_readiness.py":
        return False
    return is_regular_file_without_symlinks(path, ROOT)


def snippet(line: str, start: int, end: int) -> str:
    left = max(0, start - 40)
    right = min(len(line), end + 40)
    value = line[left:right].strip()
    value = re.sub(r"\s+", " ", value)
    return value[:160]


def mask_http_urls(line: str) -> str:
    """Keep character offsets while excluding URL paths from local-path scans."""

    return HTTP_URL_RE.sub(lambda match: " " * len(match.group(0)), line)


def collect_findings() -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for relative in git_files():
        path = ROOT / relative
        if not is_regular_file_without_symlinks(path, ROOT):
            continue
        forbidden_suffix = matching_suffix(path, FORBIDDEN_ATTACHMENT_SUFFIXES)
        image_suffix = matching_suffix(path, IMAGE_MEDIA_SUFFIXES)
        if forbidden_suffix:
            findings.append(
                {
                    "path": relative,
                    "line": 0,
                    "category": "forbidden_attachment",
                    "severity": "fail",
                    "match": forbidden_suffix,
                    "context": "source document, archive, or model artifact is forbidden in ordinary Git",
                }
            )
            continue
        if image_suffix:
            findings.append(
                {
                    "path": relative,
                    "line": 0,
                    "category": "binary_attachment",
                    "severity": "warn",
                    "match": image_suffix,
                    "context": "image media should be reviewed for size and publication intent",
                }
            )
            continue
        if not is_scannable(path):
            continue
        text = read_text(path)
        for line_no, line in enumerate(text.splitlines(), 1):
            local_path_text = mask_http_urls(line)
            for match in EXAMPLE_PASSWORD_RE.finditer(line):
                findings.append(
                    {
                        "path": relative,
                        "line": line_no,
                        "category": "example_password",
                        "severity": "warn",
                        "match": match.group(0),
                        "context": snippet(line, match.start(), match.end()),
                    }
                )
            for pattern in ABSOLUTE_PATH_PATTERNS:
                for match in pattern.finditer(local_path_text):
                    findings.append(
                        {
                            "path": relative,
                            "line": line_no,
                            "category": "absolute_path",
                            "severity": "warn",
                            "match": match.group(0),
                            "context": snippet(line, match.start(), match.end()),
                        }
                    )
            for label, pattern in SECRET_PATTERNS:
                for match in pattern.finditer(line):
                    findings.append(
                        {
                            "path": relative,
                            "line": line_no,
                            "category": label,
                            "severity": "warn",
                            "match": match.group(0)[:12] + "...",
                            "context": snippet(line, match.start(), match.end()),
                        }
                    )
    return findings


def build_payload(strict: bool) -> dict[str, object]:
    findings = collect_findings()
    strict_failures = [item for item in findings if item["category"] in STRICT_FAILURE_CATEGORIES]
    return {
        "files_scanned": len([relative for relative in git_files() if is_scannable(ROOT / relative)]),
        "findings": findings,
        "finding_count": len(findings),
        "strict_failure_count": len(strict_failures) if strict else 0,
        "strict_failures": strict_failures[:100],
    }


def print_human(payload: dict[str, object], strict: bool) -> None:
    print(f"public_readiness_files_scanned {payload['files_scanned']}")
    print(f"public_readiness_findings {payload['finding_count']}")
    if strict:
        print(f"public_readiness_strict_failures {payload['strict_failure_count']}")
    for item in payload["findings"][:100]:
        prefix = "FAIL" if strict and item["category"] in STRICT_FAILURE_CATEGORIES else "WARN"
        print(
            f"{prefix} {item['category']} {item['path']}:{item['line']} "
            f"{item['match']} | {item['context']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail on forbidden attachments, real secret patterns, or absolute paths",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    payload = build_payload(args.strict)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_human(payload, args.strict)
    return 1 if args.strict and payload["strict_failure_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
