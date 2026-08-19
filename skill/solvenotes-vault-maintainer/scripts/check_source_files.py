#!/usr/bin/env python3
"""Check source presence and extractability without asserting semantic coverage."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import zipfile
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.etree import ElementTree

from notes_utils import manifest_rows

WEAK_HIT_COUNT_RE = re.compile(r"(?P<count>\d+)\s*个(?:原)?关键词弱命中(?:单元)?")
SUPPORTED_EXTRACTABILITY_SUFFIXES = {".pdf", ".pptx", ".docx"}
SEMANTIC_COMPLETENESS_CLAIMS = ("可抽取文本已覆盖", "语义覆盖完成", "完整覆盖", "已全部覆盖")
ISSUE_CODE_MARKERS = (
    ("SOURCE_ROOT_UNAVAILABLE", "source root"),
    ("SOURCE_MISSING", "missing source file"),
    ("EXTRACTOR_FAILED", "extractability probe failed"),
    ("NO_EXTRACTABLE_TEXT", "source has no extractable text"),
    ("EXTRACTABLE_UNIT_COUNT_MISMATCH", "extractable unit count mismatch"),
    ("BLANK_UNDER_COMPLETE_TEXT", "blank extractable units conflict"),
    ("BLANK_LIMITATION_MISSING", "blank extractable units are not explicitly recorded"),
)


@dataclass(frozen=True)
class ExtractabilityEvidence:
    source: str
    kind: str
    expected_units: int | None
    observed_units: int | None
    blank_units: tuple[int, ...]
    has_extractable_text: bool


def issue_code(issue: str) -> str:
    for code, marker in ISSUE_CODE_MARKERS:
        if marker in issue:
            return code
    return "OTHER_SOURCE_FILE_ISSUE"


def configured_source_root(arg_value: Path | None) -> Path | None:
    if arg_value is not None:
        return arg_value.expanduser()
    env = os.environ.get("SOLVENOTES_SOURCE_ROOT")
    if env:
        return Path(env).expanduser()
    return None


def suspicious_pdf_text_claim(cells: list[str]) -> bool:
    """Detect the old one-weak-hit-per-page completeness contradiction."""

    if len(cells) < 8:
        return False
    source = cells[0].strip("`")
    if Path(source).suffix.lower() != ".pdf":
        return False
    page_match = re.fullmatch(r"\d+", cells[2])
    weak_match = WEAK_HIT_COUNT_RE.search(cells[7])
    if page_match is None or weak_match is None:
        return False
    claims_extractable_coverage = "可抽取文本" in cells[5] and "覆盖" in cells[5]
    return claims_extractable_coverage and int(page_match.group()) == int(weak_match.group("count"))


def _positive_count(cells: list[str]) -> int | None:
    if len(cells) < 3 or not cells[2].isdigit() or int(cells[2]) <= 0:
        return None
    return int(cells[2])


def _mentioned_units(text: str) -> set[int]:
    units = {int(value) for value in re.findall(r"\d+", text)}
    for match in re.finditer(r"(\d+)\s*[-–~至]\s*(\d+)", text):
        start, end = map(int, match.groups())
        if start <= end and end - start <= 10000:
            units.update(range(start, end + 1))
    return units


def _all_units_marked_blank(text: str, blank_units: tuple[int, ...], expected: int | None) -> bool:
    """Accept an explicit whole-document blank statement without listing every unit."""

    if expected is None or blank_units != tuple(range(1, expected + 1)):
        return False
    blank_marked = any(marker in text for marker in ("空白", "无可读", "未抽到"))
    return "均" in text and str(expected) in text and blank_marked


def _known_no_text_limitation(
    cells: list[str],
    *,
    expected: int | None,
    observed: int | None,
    blank_units: tuple[int, ...],
) -> bool:
    """Accept a deliberately narrow, auditable exception for visual-only files.

    A source with no text layer is not evidence of its visual content.  Strict
    mode can therefore waive the extractability failure only for a row that
    explicitly records a whole-document visual-page check, no OCR, and no
    claim of complete semantic coverage.  Any missing or ambiguous field stays
    fatal.
    """

    if len(cells) < 8 or expected is None or observed != expected:
        return False
    method = cells[3].strip().lower()
    coverage = cells[5].strip()
    limitations = cells[7].strip()
    if method != "visual-page-check" or not coverage.startswith("仅映射："):
        return False
    if not any(marker in coverage for marker in ("文本层无可抽取", "无可抽取文本")):
        return False
    if any(claim in coverage for claim in SEMANTIC_COMPLETENESS_CLAIMS):
        return False
    if not _all_units_marked_blank(limitations, blank_units, expected):
        return False
    if not re.search(r"(?:未做|未进行)\s*OCR|OCR\s*(?:未做|未进行)", limitations, flags=re.IGNORECASE):
        return False
    return "完整语义覆盖" in limitations and any(
        marker in limitations for marker in ("不证明", "不声称", "不构成")
    )


def _pdf_units(
    source_path: Path,
    run_command: Callable[..., subprocess.CompletedProcess[str]],
) -> tuple[list[str] | None, str | None]:
    try:
        result = run_command(
            ["pdftotext", "-layout", str(source_path), "-"],
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return None, "pdftotext is unavailable"
    if result.returncode:
        return None, "pdftotext failed"
    units = result.stdout.split("\f")
    if units and not units[-1].strip():
        units.pop()
    return units, None


def _xml_text_units(source_path: Path, pattern: re.Pattern[str]) -> tuple[list[str] | None, str | None]:
    try:
        with zipfile.ZipFile(source_path) as archive:
            members: list[tuple[int, str]] = []
            for name in archive.namelist():
                match = pattern.fullmatch(name)
                if match:
                    members.append((int(match.group(1)), name))
            units: list[str] = []
            for _, name in sorted(members):
                root = ElementTree.fromstring(archive.read(name))
                units.append(" ".join((node.text or "").strip() for node in root.iter() if node.tag.endswith("}t")))
    except (OSError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        return None, f"OpenXML extraction failed: {exc.__class__.__name__}"
    return units, None


def _docx_has_text(source_path: Path) -> tuple[bool | None, str | None]:
    try:
        with zipfile.ZipFile(source_path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
    except (KeyError, OSError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        return None, f"DOCX extraction failed: {exc.__class__.__name__}"
    return any((node.text or "").strip() for node in root.iter() if node.tag.endswith("}t")), None


def source_extractability_issues(
    source_root: Path,
    rows: list[tuple[Path, list[str]]],
    *,
    strict: bool,
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[list[str], list[ExtractabilityEvidence], int]:
    """Probe PDF/PPTX/DOCX text layers in strict mode.

    The result establishes only whether text can be extracted and, for PDF and
    PPTX, which declared pages/slides are blank.  It never endorses raw cells or
    treats extracted text as proof of semantic note coverage.
    """

    if not strict:
        return [], [], 0

    issues: list[str] = []
    evidence: list[ExtractabilityEvidence] = []
    unsupported = 0
    pptx_pattern = re.compile(r"ppt/slides/slide(\d+)\.xml")
    for _, cells in rows:
        if not cells:
            continue
        source = cells[0].strip("`")
        suffix = Path(source).suffix.lower()
        source_path = source_root / source
        if not source_path.is_file():
            continue
        if suffix not in SUPPORTED_EXTRACTABILITY_SUFFIXES:
            unsupported += 1
            continue
        expected = _positive_count(cells)
        units: list[str] | None = None
        error: str | None = None
        observed: int | None = None
        blank_units: tuple[int, ...] = ()
        has_text = False
        if suffix == ".pdf":
            units, error = _pdf_units(source_path, run_command)
        elif suffix == ".pptx":
            units, error = _xml_text_units(source_path, pptx_pattern)
        else:
            docx_has_text, error = _docx_has_text(source_path)
            has_text = bool(docx_has_text)

        if error:
            issues.append(f"extractability probe failed for {source}: {error}")
            evidence.append(ExtractabilityEvidence(source, suffix, expected, None, (), False))
            continue
        if units is not None:
            observed = len(units)
            blank_units = tuple(index for index, text in enumerate(units, 1) if not text.strip())
            has_text = any(text.strip() for text in units)
        row_evidence = ExtractabilityEvidence(source, suffix, expected, observed, blank_units, has_text)
        evidence.append(row_evidence)
        if expected is not None and observed is not None and expected != observed:
            issues.append(f"extractable unit count mismatch for {source}: manifest={expected} observed={observed}")
        coverage_status = cells[5] if len(cells) > 5 else ""
        limitations = cells[7] if len(cells) > 7 else ""
        known_no_text = _known_no_text_limitation(
            cells,
            expected=expected,
            observed=observed,
            blank_units=blank_units,
        )
        if not has_text and not known_no_text:
            issues.append(
                f"source has no extractable text without a complete known-limitation contract: {source}; "
                "require visual-page-check, whole-document blank units, OCR-not-done, and no-complete-semantics wording"
            )
        if blank_units and "可抽取文本已覆盖" in coverage_status:
            preview = ",".join(str(unit) for unit in blank_units[:20])
            issues.append(
                f"blank extractable units conflict with complete-text wording for {source}: units={preview}; "
                "record extractability separately from semantic coverage"
            )
        blank_marked = any(marker in limitations for marker in ("空白", "无可读", "未抽到"))
        named_blank_units = set(blank_units).issubset(_mentioned_units(limitations))
        whole_document_blank = _all_units_marked_blank(limitations, blank_units, expected)
        if blank_units and (not blank_marked or not (named_blank_units or whole_document_blank)):
            preview = ",".join(str(unit) for unit in blank_units[:20])
            issues.append(
                f"blank extractable units are not explicitly recorded in limitations for {source}: units={preview}"
            )
    return issues, evidence, unsupported


def pdf_text_consistency_issues(
    source_root: Path,
    rows: list[tuple[Path, list[str]]],
    *,
    strict: bool,
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[list[str], int]:
    """Compatibility helper for the former suspicious-PDF-only contract."""

    if not strict:
        return [], 0
    suspicious_rows = [row for row in rows if suspicious_pdf_text_claim(row[1])]
    issues, evidence, _unsupported = source_extractability_issues(
        source_root,
        suspicious_rows,
        strict=True,
        run_command=run_command,
    )
    return issues, len(evidence)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--strict", action="store_true", help="fail when the source root is unavailable")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    source_root = configured_source_root(args.source_root)
    rows = manifest_rows()
    issues: list[str] = []
    missing_source_issues: list[str] = []
    extractability_issues: list[str] = []
    extractability_evidence: list[ExtractabilityEvidence] = []
    unsupported_extractability_rows = 0
    skipped = False
    source_root_label = "<未配置 SOLVENOTES_SOURCE_ROOT>"
    source_dirs = {cells[0].strip("`").split("/", 1)[0] for _, cells in rows if cells}
    if source_root is None:
        skipped = True
        if args.strict:
            issues.append("source root is not configured; set SOLVENOTES_SOURCE_ROOT or pass --source-root")
    else:
        source_root = source_root.resolve()
        source_root_label = str(source_root)
        source_dirs_present = any((source_root / directory).exists() for directory in source_dirs)
        if not source_root.exists() or not source_dirs_present:
            skipped = True
            if args.strict:
                issues.append(f"source root or course source directories are unavailable: {source_root}")
        else:
            for _, cells in rows:
                if len(cells) < 1:
                    continue
                source = cells[0].strip("`")
                if not (source_root / source).exists():
                    issue = f"missing source file: {source_root / source}"
                    missing_source_issues.append(issue)
                    issues.append(issue)
            extractability_issues, extractability_evidence, unsupported_extractability_rows = (
                source_extractability_issues(source_root, rows, strict=args.strict)
            )
            issues.extend(extractability_issues)

    blank_units = sum(len(item.blank_units) for item in extractability_evidence)
    payload = {
        "source_root": source_root_label,
        "manifest_source_rows": len(rows),
        "source_file_check_skipped": skipped,
        "extractability_checks": len(extractability_evidence),
        "unsupported_extractability_rows": unsupported_extractability_rows,
        "blank_extractable_units": blank_units,
        "missing_source_files": len(missing_source_issues),
        "extractability_issues": len(extractability_issues),
        "source_file_issues": len(issues),
        "issue_counts": dict(sorted(Counter(issue_code(issue) for issue in issues).items())),
        "blank_unit_evidence": [
            {"source": item.source, "units": item.blank_units}
            for item in extractability_evidence
            if item.blank_units
        ],
        "extractability_evidence": [asdict(item) for item in extractability_evidence[:100]],
        "coded_issues": [{"code": issue_code(issue), "message": issue} for issue in issues[:100]],
        "issues": issues[:100],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"source_root {source_root_label}")
        print(f"manifest_source_rows {len(rows)}")
        print(f"source_file_check_skipped {int(skipped)}")
        print(f"extractability_checks {len(extractability_evidence)}")
        print(f"unsupported_extractability_rows {unsupported_extractability_rows}")
        print(f"blank_extractable_units {blank_units}")
        print(f"missing_source_files {len(missing_source_issues)}")
        print(f"extractability_issues {len(extractability_issues)}")
        print(f"source_file_issues {len(issues)}")
        for issue in issues[:100]:
            print(f"ISSUE {issue_code(issue)} {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
