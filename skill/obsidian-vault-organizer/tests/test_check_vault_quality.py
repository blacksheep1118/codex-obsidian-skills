from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from typing import Optional

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_vault_quality import find_vault_issues, markdown_files  # noqa: E402


SCRIPT = ROOT / "scripts" / "check_vault_quality.py"


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


def test_vault_quality_ignores_todo_inside_balanced_fenced_code(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "example.md", "# Example\n\n```python\n# TODO: demonstrate placeholder syntax\n```\n")

    issues = find_vault_issues(vault)

    assert "template_residue" not in issue_kinds(issues)
    assert "unbalanced_fence" not in issue_kinds(issues)


def test_vault_quality_keeps_conflict_and_unbalanced_fence_checks_inside_code(tmp_path: Path):
    vault = tmp_path / "vault"
    write(
        vault / "broken.md",
        "# Broken\n\n```text\n<<<<<<< HEAD\nold\n=======\nnew\n>>>>>>> branch\n",
    )

    issues = find_vault_issues(vault)

    assert "conflict_marker" in issue_kinds(issues)
    assert "unbalanced_fence" in issue_kinds(issues)
    assert "template_residue" not in issue_kinds(issues)


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
    write(vault / "质量审查报告.md", "# Report\n\nGenerated audit.\n")

    issues = find_vault_issues(vault, forbid_report_notes=True)

    assert "report_note" in issue_kinds(issues)


def test_generic_profile_without_report_gate_keeps_default_behavior(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "99_内容覆盖审查.md", "# Legacy Audit\n")

    issues = find_vault_issues(vault, profile="generic")

    assert "report_note" not in issue_kinds(issues)


def test_generic_profile_can_allow_formal_coverage_audit_while_forbidding_other_reports(tmp_path: Path):
    vault = tmp_path / "vault"
    write(
        vault / "course" / "source_manifest.md",
        '---\nnote_type: "source_manifest"\n---\n\n# Source Manifest\n',
    )
    write(
        vault / "course" / "99_内容覆盖审查.md",
        '---\ncourse: "course"\nnote_type: "coverage_audit"\n---\n\n# Formal Coverage Audit\n',
    )
    write(vault / "course" / "质量审查报告.md", "# Report\n\nGenerated audit.\n")

    issues = find_vault_issues(
        vault,
        forbid_report_notes=True,
        allow_formal_coverage_audits=True,
        profile="generic",
    )

    report_paths = {issue.path.as_posix() for issue in issues if issue.kind == "report_note"}
    assert report_paths == {"course/质量审查报告.md"}


def test_solvenotes_profile_rejects_formal_coverage_audit_even_with_typed_manifest(tmp_path: Path):
    vault = tmp_path / "vault"
    write(
        vault / "source_manifest.md",
        '---\nnote_type: "source_manifest"\n---\n\n# Source Manifest\n',
    )
    write(
        vault / "99_内容覆盖审查.md",
        '---\nnote_type: "coverage_audit"\n---\n\n# Formal Coverage Audit\n',
    )

    issues = find_vault_issues(
        vault,
        allow_formal_coverage_audits=True,
        profile="solvenotes",
    )

    assert "report_note" in issue_kinds(issues)


def test_solvenotes_profile_alone_rejects_formal_coverage_audit_in_cli(tmp_path: Path):
    vault = tmp_path / "vault"
    write(
        vault / "source_manifest.md",
        '---\nnote_type: "source_manifest"\n---\n\n# Source Manifest\n',
    )
    write(
        vault / "99_内容覆盖审查.md",
        '---\nnote_type: "coverage_audit"\n---\n\n# Formal Coverage Audit\n',
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--profile", "solvenotes", str(vault)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "REPORT_NOTE: 99_内容覆盖审查.md" in result.stdout


@pytest.mark.parametrize(
    "note_type",
    [
        "coverage_audit",
        "global_coverage_audit",
        "vault_audit",
        "audit_record",
        "source_manifest_history",
    ],
)
def test_solvenotes_profile_rejects_report_note_type_with_innocuous_filename(
    tmp_path: Path,
    note_type: str,
):
    vault = tmp_path / "vault"
    write(
        vault / "ordinary-name.md",
        f'---\nnote_type: "{note_type}"\n---\n\n# Ordinary Name\n',
    )

    issues = find_vault_issues(vault, profile="solvenotes")

    report_paths = {issue.path.as_posix() for issue in issues if issue.kind == "report_note"}
    assert report_paths == {"ordinary-name.md"}


def test_formal_coverage_exception_requires_exact_filename_and_note_type(tmp_path: Path):
    vault = tmp_path / "vault"
    write(
        vault / "wrong-type" / "source_manifest.md",
        '---\nnote_type: "source_manifest"\n---\n\n# Source Manifest\n',
    )
    write(
        vault / "wrong-type" / "99_内容覆盖审查.md",
        '---\nnote_type: "audit_report"\n---\n\n# Wrong Type\n',
    )
    write(
        vault / "wrong-name" / "source_manifest.md",
        '---\nnote_type: "source_manifest"\n---\n\n# Source Manifest\n',
    )
    write(
        vault / "wrong-name" / "98_内容覆盖审查.md",
        '---\nnote_type: "coverage_audit"\n---\n\n# Wrong Name\n',
    )

    issues = find_vault_issues(
        vault,
        forbid_report_notes=True,
        allow_formal_coverage_audits=True,
        profile="generic",
    )

    report_paths = {issue.path.as_posix() for issue in issues if issue.kind == "report_note"}
    assert report_paths == {
        "wrong-name/98_内容覆盖审查.md",
        "wrong-type/99_内容覆盖审查.md",
    }


@pytest.mark.parametrize(
    "manifest_text",
    [
        None,
        '---\nnote_type: "course_manifest"\n---\n\n# Wrong Manifest Type\n',
    ],
    ids=["missing-manifest", "wrong-manifest-type"],
)
def test_formal_coverage_exception_requires_valid_sibling_manifest(
    tmp_path: Path,
    manifest_text: Optional[str],
):
    vault = tmp_path / "vault"
    course = vault / "course"
    if manifest_text is not None:
        write(course / "source_manifest.md", manifest_text)
    write(
        course / "99_内容覆盖审查.md",
        '---\nnote_type: "coverage_audit"\n---\n\n# Formal Coverage Audit\n',
    )

    issues = find_vault_issues(
        vault,
        forbid_report_notes=True,
        allow_formal_coverage_audits=True,
        profile="generic",
    )

    report_paths = {issue.path.as_posix() for issue in issues if issue.kind == "report_note"}
    assert report_paths == {"course/99_内容覆盖审查.md"}


def test_formal_coverage_exception_rejects_manifest_filename_case_alias(tmp_path: Path):
    vault = tmp_path / "vault"
    course = vault / "course"
    write(
        course / "SOURCE_MANIFEST.md",
        '---\nnote_type: "source_manifest"\n---\n\n# Source Manifest\n',
    )
    write(
        course / "99_内容覆盖审查.md",
        '---\nnote_type: "coverage_audit"\n---\n\n# Formal Coverage Audit\n',
    )

    issues = find_vault_issues(
        vault,
        forbid_report_notes=True,
        allow_formal_coverage_audits=True,
        profile="generic",
    )

    report_paths = {issue.path.as_posix() for issue in issues if issue.kind == "report_note"}
    assert report_paths == {"course/99_内容覆盖审查.md"}


def test_formal_coverage_manifest_directory_is_report_note_cli_failure(tmp_path: Path):
    vault = tmp_path / "vault"
    course = vault / "course"
    (course / "source_manifest.md").mkdir(parents=True)
    write(
        course / "99_内容覆盖审查.md",
        '---\nnote_type: "coverage_audit"\n---\n\n# Formal Coverage Audit\n',
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--profile",
            "generic",
            "--forbid-report-notes",
            "--allow-formal-coverage-audits",
            str(vault),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "REPORT_NOTE: course/99_内容覆盖审查.md" in result.stdout


def test_markdown_files_excludes_internal_markdown_symlinks(tmp_path: Path):
    vault = tmp_path / "vault"
    target = vault / "target.md"
    alias = vault / "alias.md"
    write(target, "# Target\n")
    alias.symlink_to(target)

    paths = [path.relative_to(vault).as_posix() for path in markdown_files(vault)]

    assert paths == ["target.md"]


def test_vault_quality_excludes_guidance_tooling_cache_and_external_symlink(tmp_path: Path):
    write(tmp_path / "Actual.md", "# Actual\n")
    write(tmp_path / "AGENT.md", "# Guidance\n<<<<<<< should not be scanned\n")
    write(tmp_path / "scripts" / "README.md", "# Tooling\nTODO\n")
    write(tmp_path / ".pytest_cache" / "README.md", "# Cache\n<<<<<<< should not be scanned\n")
    outside = tmp_path.parent / "luna-quality-outside.md"
    write(outside, "# Outside\n<<<<<<< should not be scanned\n")
    (tmp_path / "linked.md").symlink_to(outside)

    issues = find_vault_issues(tmp_path)

    assert issues == []


def test_skip_dir_excludes_independent_nested_topic_and_nested_passes_alone(tmp_path: Path):
    parent = tmp_path / "course"
    nested = parent / "nested-topic"
    write(parent / "source_manifest.md", "# Parent manifest\n")
    write(nested / "source_manifest.md", "# Nested manifest\n")

    parent_issues = find_vault_issues(parent)
    skipped_parent_issues = find_vault_issues(
        parent,
        skip_dirs=[Path("nested-topic")],
    )
    nested_issues = find_vault_issues(nested)

    assert "duplicate_stem" in issue_kinds(parent_issues)
    assert skipped_parent_issues == []
    assert nested_issues == []


def test_skip_dir_is_exact_root_relative_directory_and_repeatable(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "topic" / "ignored.md", "# Ignored\n\nTODO\n")
    write(vault / "topic.md", "# Same-name file\n\nTODO\n")
    write(vault / "topic-similar" / "visible.md", "# Similar directory\n\nTODO\n")

    issues = find_vault_issues(
        vault,
        skip_dirs=[Path("topic"), Path("topic")],
    )

    residue_paths = {
        issue.path.as_posix()
        for issue in issues
        if issue.kind == "template_residue"
    }
    assert residue_paths == {"topic.md", "topic-similar/visible.md"}


def test_skip_dir_rejects_missing_non_directory_and_all_symlink_components(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "note.md", "# Note\n")
    write(vault / "real" / "nested" / "note.md", "# Real\n")
    (vault / "alias").symlink_to(vault / "real", target_is_directory=True)
    outside = tmp_path / "outside"
    write(outside / "note.md", "# Outside\n")
    (vault / "external").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="does not exist"):
        markdown_files(vault, skip_dirs=[Path("missing")])
    with pytest.raises(ValueError, match="not a directory"):
        markdown_files(vault, skip_dirs=[Path("note.md")])
    with pytest.raises(ValueError, match="symlink component.*alias"):
        markdown_files(vault, skip_dirs=[Path("alias")])
    with pytest.raises(ValueError, match="symlink component.*alias"):
        markdown_files(vault, skip_dirs=[Path("alias/nested")])
    with pytest.raises(ValueError, match="symlink component.*external"):
        markdown_files(vault, skip_dirs=[Path("external")])


def test_skip_dir_rejects_noncanonical_component_spelling_on_any_filesystem(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "CanonicalTopic" / "NestedPart" / "note.md", "# Canonical\n")

    with pytest.raises(ValueError, match="non-canonical spelling.*canonicaltopic.*CanonicalTopic"):
        markdown_files(vault, skip_dirs=[Path("canonicaltopic")])
    with pytest.raises(ValueError, match="non-canonical spelling.*nestedpart.*NestedPart"):
        markdown_files(vault, skip_dirs=[Path("CanonicalTopic/nestedpart")])


def test_skip_dir_canonical_nested_paths_are_effective(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "real" / "nested" / "ignored.md", "# Ignored\n\nTODO\n")
    write(vault / "real" / "visible.md", "# Visible\n")

    nested_only = markdown_files(vault, skip_dirs=[Path("real/nested")])
    entire_real = markdown_files(vault, skip_dirs=[Path("real")])

    assert [path.relative_to(vault).as_posix() for path in nested_only] == [
        "real/visible.md"
    ]
    assert entire_real == []


def test_cli_skip_dir_is_repeatable_and_nested_topic_is_checked_separately(tmp_path: Path):
    parent = tmp_path / "course"
    nested = parent / "nested-topic"
    write(parent / "source_manifest.md", "# Parent manifest\n")
    write(nested / "source_manifest.md", "# Nested manifest\n")

    without_skip = subprocess.run(
        [sys.executable, str(SCRIPT), str(parent)],
        text=True,
        capture_output=True,
    )
    with_repeated_skip = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--skip-dir",
            "nested-topic",
            "--skip-dir",
            "nested-topic",
            str(parent),
        ],
        text=True,
        capture_output=True,
    )
    nested_result = subprocess.run(
        [sys.executable, str(SCRIPT), str(nested)],
        text=True,
        capture_output=True,
    )

    assert without_skip.returncode == 1
    assert "DUPLICATE_STEM" in without_skip.stdout
    assert with_repeated_skip.returncode == 0
    assert nested_result.returncode == 0


def test_cli_skip_dir_rejects_symlink_and_noncanonical_aliases(tmp_path: Path):
    vault = tmp_path / "vault"
    write(vault / "CanonicalTopic" / "note.md", "# Canonical\n")
    (vault / "alias").symlink_to(
        vault / "CanonicalTopic",
        target_is_directory=True,
    )

    symlink_result = subprocess.run(
        [sys.executable, str(SCRIPT), "--skip-dir", "alias", str(vault)],
        text=True,
        capture_output=True,
    )
    case_result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--skip-dir",
            "canonicaltopic",
            str(vault),
        ],
        text=True,
        capture_output=True,
    )
    canonical_result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--skip-dir",
            "CanonicalTopic",
            str(vault),
        ],
        text=True,
        capture_output=True,
    )

    assert symlink_result.returncode == 2
    assert "symlink component" in symlink_result.stderr
    assert case_result.returncode == 2
    assert "non-canonical spelling" in case_result.stderr
    assert canonical_result.returncode == 0
