#!/usr/bin/env python3
"""Check formula blocks for structural and extraction-quality problems."""

from __future__ import annotations

import argparse
import json
import re
import sys

from notes_utils import markdown_files, read_text, rel, text_without_code

BAD_LATEX_PATTERNS = [
    (re.compile(r"\\\\(theta|frac|top|rightarrow|nabla|sum|prod|alpha|beta|lambda)"), "double-escaped LaTeX command"),
    (re.compile(r"\\$"), "dangling backslash"),
]


def block_formulas(text: str) -> list[str]:
    parts = text_without_code(text).split("$$")
    return parts[1::2] if len(parts) > 1 else []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    issues: list[str] = []
    formula_blocks = 0
    files_with_formulas = 0
    for path in markdown_files():
        text = read_text(path)
        formulas = block_formulas(text)
        if formulas:
            files_with_formulas += 1
        formula_blocks += len(formulas)
        prose_text = text_without_code(text)
        if prose_text.count("$$") % 2:
            issues.append(f"{rel(path)}: unbalanced $$ delimiters")
        for idx, formula in enumerate(formulas, 1):
            if "�" in formula:
                issues.append(f"{rel(path)}: formula block {idx} contains replacement character")
            for pattern, label in BAD_LATEX_PATTERNS:
                if pattern.search(formula):
                    issues.append(f"{rel(path)}: formula block {idx} has {label}")

    payload = {
        "formula_files": files_with_formulas,
        "formula_blocks": formula_blocks,
        "formula_issues": len(issues),
        "issues": issues[:100],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"formula_files {files_with_formulas}")
        print(f"formula_blocks {formula_blocks}")
        print(f"formula_issues {len(issues)}")
        for issue in issues[:100]:
            print(f"ISSUE {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
