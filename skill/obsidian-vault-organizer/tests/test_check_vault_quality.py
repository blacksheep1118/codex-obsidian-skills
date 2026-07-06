from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_vault_quality import find_vault_issues


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def issue_kinds(issues) -> set[str]:
    return {issue.kind for issue in issues}


def test_vault_quality_reports_generic_issues_and_duplicate_stems(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "a" / "topic.md", "# Topic A\n")
    write(vault / "b" / "topic.md", "# Topic B\n")
    write(vault / "empty.md", "")
    write(vault / "conflict.md", "# Conflict\n\n<<<<<<< HEAD\nold\n=======\nnew\n>>>>>>> branch\n")
    write(vault / "template.md", "# Template\n\n相关知识链接：TODO\n")

    issues = find_vault_issues(vault)

    assert {"duplicate_stem", "empty_file", "conflict_marker", "template_residue"}.issubset(issue_kinds(issues))


def test_bridge_notes_do_not_create_duplicate_stem_issues(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "current" / "legacy.md", "# Legacy\n\nCurrent content.\n")
    write(vault / "old" / "legacy.md", "# 旧入口\n\n本页保留旧路径，正文请读 [[current/legacy]]。\n")

    issues = find_vault_issues(vault)

    assert "duplicate_stem" not in issue_kinds(issues)


def test_solvenotes_profile_controls_project_specific_strict_residue(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "note.md", "# Note\n\n这句话包含神谕式残留。\n\n## 知识链接\n")

    generic_issues = find_vault_issues(vault, strict_study=True)
    solvenotes_issues = find_vault_issues(vault, strict_study=True, profile="solvenotes")

    assert "link_dump_section" in issue_kinds(generic_issues)
    assert "strict_study_residue" not in issue_kinds(generic_issues)
    assert "strict_study_residue" in issue_kinds(solvenotes_issues)


def test_pattern_file_adds_custom_residue_patterns(tmp_path: Path):
    vault = tmp_path / "vault"
    patterns = tmp_path / "patterns.txt"
    patterns.write_text("text:custom placeholder\nregex:自定义\\d+\n", encoding="utf-8")
    write(vault / "note.md", "# Note\n\nThis has custom placeholder.\n\n这里有自定义42。\n")

    issues = find_vault_issues(vault, pattern_files=[patterns])

    strict_hits = [issue for issue in issues if issue.kind == "strict_study_residue"]
    assert len(strict_hits) == 2


def test_forbid_report_notes_flags_audit_notes(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "99_质量审查报告.md", "# Report\n\nGenerated audit.\n")

    issues = find_vault_issues(vault, forbid_report_notes=True)

    assert "report_note" in issue_kinds(issues)
