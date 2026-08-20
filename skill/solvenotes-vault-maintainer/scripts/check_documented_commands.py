#!/usr/bin/env python3
"""Check that maintenance paths written in workspace guidance still exist."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])((?:skill/)?[A-Za-z0-9_.-]+/(?:scripts|tests|references|agents)/[A-Za-z0-9_.-]+|scripts/[A-Za-z0-9_.-]+|notes/\.github/[A-Za-z0-9_./-]+|agent/[A-Za-z0-9_./-]+)"
)
IGNORED_PREFIXES = ("/path/to/", "/absolute/path/to/", "<", "${")


def guidance_files(workspace_root: Path, skills_root: Path) -> list[Path]:
    candidates = [
        workspace_root / "AGENT.md",
        workspace_root / "notes" / "AGENT.md",
        workspace_root / "notes" / "README.md",
        skills_root / "README.md",
        skills_root / "CONTRIBUTING.md",
        *sorted((workspace_root / "agent").glob("*.md")),
        *sorted(skills_root.glob("skill/*/SKILL.md")),
    ]
    return [path for path in candidates if path.is_file()]


def resolve_token(
    token: str,
    source: Path,
    line: str,
    active_skill: str | None,
    workspace_root: Path,
    skills_root: Path,
) -> Path | None:
    if token.startswith(IGNORED_PREFIXES):
        return None
    if token.startswith("skill/"):
        return skills_root / token
    if token.startswith("notes/") or token.startswith("agent/"):
        return workspace_root / token
    if token.startswith("scripts/"):
        if active_skill:
            return skills_root / "skill" / active_skill / token
        if source == workspace_root / "AGENT.md":
            return skills_root / token
        try:
            relative = source.relative_to(skills_root)
        except ValueError:
            relative = None
        if "skills repository root" in line.lower():
            return skills_root / token
        if relative is not None and len(relative.parts) >= 3 and relative.parts[0] == "skill":
            return source.parent / token
        return None
    return None


def scan(workspace_root: Path, skills_root: Path) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    references = 0
    for source in guidance_files(workspace_root, skills_root):
        text = source.read_text(encoding="utf-8")
        active_skill: str | None = None
        in_fence = False
        for line_number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith(("```", "~~~")):
                in_fence = not in_fence
                if not in_fence:
                    active_skill = None
                continue
            if in_fence:
                context = re.search(r"\bcd\s+skill[/\\]([A-Za-z0-9_.-]+)", line)
                if context and "<" not in context.group(1):
                    active_skill = context.group(1)
            for match in PATH_RE.finditer(line):
                token = match.group(1)
                target = resolve_token(token, source, line, active_skill, workspace_root, skills_root)
                if target is None:
                    continue
                references += 1
                if not target.is_file():
                    issues.append(
                        {
                            "path": str(source.relative_to(workspace_root)),
                            "line": line_number,
                            "token": token,
                            "resolved": str(target),
                        }
                    )
    return {
        "files_checked": len(guidance_files(workspace_root, skills_root)),
        "references_checked": references,
        "issues": issues,
        "issue_count": len(issues),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--skills-root", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    workspace_root = args.workspace_root.expanduser().absolute()
    skills_root = (args.skills_root or workspace_root / "skills").expanduser().absolute()
    payload = scan(workspace_root, skills_root)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"documented_commands_files_checked {payload['files_checked']}")
        print(f"documented_commands_references_checked {payload['references_checked']}")
        print(f"documented_commands_issues {payload['issue_count']}")
        for issue in payload["issues"]:
            print(f"ERROR {issue['path']}:{issue['line']} {issue['token']} -> {issue['resolved']}")
    return 1 if args.strict and payload["issue_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
