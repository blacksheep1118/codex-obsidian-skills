#!/usr/bin/env python3
"""Check the small guidance surface shared by Notes, Skills, and Agent."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ABSOLUTE_MACHINE_PATH = re.compile(r"(?:/Users/|/opt/anaconda3|/opt/homebrew|[A-Za-z]:\\Users\\)")
SHA_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])")
NOTES_WORKFLOW_PACKAGE_MODE = re.compile(r"(?m)^\s*-\s*package\s*(?:#.*)?$")
NOTES_WORKFLOW_PACKAGE_ENTRYPOINT = re.compile(
    r"\b(?:package_(?:vault|workspace)|verify_(?:vault|workspace)_package)\.py\b"
)


def scan(workspace_root: Path) -> dict[str, object]:
    root = workspace_root.resolve()
    issues: list[str] = []
    required = (root / "AGENT.md", root / "agent", root / "notes", root / "skills")
    for path in required:
        if not path.exists():
            issues.append(f"missing workspace object: {path.relative_to(root)}")
    if (root / "agents").exists():
        issues.append("agents/: duplicate plural Agent directory is forbidden")
    guidance_paths = [root / "AGENT.md", root / "notes" / "AGENT.md", *sorted((root / "agent").glob("*.md"))]
    for path in guidance_paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if ABSOLUTE_MACHINE_PATH.search(text):
            issues.append(f"{path.relative_to(root)}: machine-specific absolute path")
    lock = root / "notes" / ".github" / "solvenotes-skills.lock.json"
    locked_sha: str | None = None
    if lock.is_file():
        try:
            payload = json.loads(lock.read_text(encoding="utf-8"))
            locked_sha = payload.get("commit")
            if not isinstance(locked_sha, str) or not SHA_RE.fullmatch(locked_sha):
                issues.append("Notes lock commit is not a full SHA")
        except json.JSONDecodeError as exc:
            issues.append(f"Notes lock is invalid JSON: {exc}")
    else:
        issues.append("missing Notes Skills lock")
    workflow = root / "notes" / ".github" / "workflows" / "vault-quality.yml"
    if workflow.is_file():
        workflow_text = workflow.read_text(encoding="utf-8")
        if locked_sha:
            for sha in SHA_RE.findall(workflow_text):
                if sha != locked_sha:
                    issues.append(f"vault workflow contains a SHA not sourced from lock: {sha}")
            if "solvenotes-skills.lock.json" not in workflow_text:
                issues.append("vault workflow does not read the Skills lock")
        if NOTES_WORKFLOW_PACKAGE_MODE.search(workflow_text):
            issues.append("vault workflow exposes forbidden package mode")
        for entrypoint in sorted(set(NOTES_WORKFLOW_PACKAGE_ENTRYPOINT.findall(workflow_text))):
            issues.append(f"vault workflow invokes forbidden package entry point: {entrypoint}")
    return {"ok": not issues, "root": str(root), "files_checked": len(guidance_paths), "issues": sorted(set(issues))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = scan(args.workspace_root)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"workspace_guidance_files_checked {payload['files_checked']}")
        print(f"workspace_guidance_issues {len(payload['issues'])}")
        for issue in payload["issues"]:
            print(f"ISSUE {issue}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
