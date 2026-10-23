from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from scripts.check_web_notes import load_manifest_rows
from scripts.collect_web_sources import build_manifest, collect_sources


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_web_notes.py"
SUBPROCESS_TIMEOUT_SECONDS = 60


def run_checker(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_entry_map(collection: Path) -> None:
    write(collection / "00_Learning_Map.md", "# Learning Map\n\n[[01_Course]]\n")


def manifest(
    source: str,
    resource: str | None = None,
    *,
    page_kind: str = "course_page",
    resources: list[tuple[str, str, str, str]] | None = None,
) -> str:
    learning_rows = ""
    if resource:
        resources = [(resource, "listed", "listed", "")]
    for resource_url, access, status, error in resources or []:
        learning_rows += f"| pdf | Paper PDF | {resource_url} | {access} | {status} | {error} | {source} |\n"
    return (
        "# Source Manifest\n\n"
        "## Pages\n\n"
        "| Kind | Title | Original Source | URL | Access | Status | Error | Description |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
        f"| {page_kind} | Course | {source} | {source} | ok | ok |  | Course page |\n"
        "\n"
        "## Learning Resources\n\n"
        "| Kind | Title | URL | Access | Status | Error | Source Page |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        f"{learning_rows}"
    )


def test_check_web_notes_fails_on_scaffold_residue_and_missing_user_source(tmp_path: Path):
    collection = tmp_path / "collection"
    source = "https://example.com/course"
    write(collection / "source_manifest.md", manifest(source))
    write_entry_map(collection)
    write(
        collection / "01_Course.md",
        "---\nstatus: scaffold\n---\n\n# Course\n\n- 待补充: source details.\n",
    )

    result = run_checker(collection, "--source", source, "--source", "https://example.com/missing")

    assert result.returncode == 1
    assert "SCAFFOLD_RESIDUE" in result.stdout
    assert "MISSING_USER_SOURCE" in result.stdout


@pytest.mark.parametrize(
    "code_block",
    [
        "```python\n# TODO: upstream example\npass\n```",
        "~~~text\nTo complete: literal source text\n~~~",
        "`TODO: inline code`",
        "    TODO: indented code",
        "> ```text\n> 待补充: quoted code\n> ```",
        "- ```text\n  TODO: list code\n  ```",
    ],
    ids=("fenced", "tilde", "inline", "indented", "blockquote", "list"),
)
def test_check_web_notes_ignores_scaffold_words_in_commonmark_code(
    tmp_path: Path,
    code_block: str,
) -> None:
    collection = tmp_path / "collection"
    source = "https://example.com/course"
    write(collection / "source_manifest.md", manifest(source))
    write_entry_map(collection)
    write(
        collection / "01_Course.md",
        f"# Course\n\nFinished source-specific explanation.\n\n{code_block}\n",
    )

    result = run_checker(collection, "--source", source)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "web_note_issues 0" in result.stdout


def test_check_web_notes_still_reports_visible_scaffold_word(tmp_path: Path) -> None:
    collection = tmp_path / "collection"
    source = "https://example.com/course"
    write(collection / "source_manifest.md", manifest(source))
    write_entry_map(collection)
    write(
        collection / "01_Course.md",
        "# Course\n\nFinished source-specific explanation.\n\nTODO: add the missing experiment.\n",
    )

    result = run_checker(collection, "--source", source)

    assert result.returncode == 1
    assert "SCAFFOLD_RESIDUE" in result.stdout


def test_check_web_notes_passes_finalized_note_and_per_link_resource(tmp_path: Path):
    collection = tmp_path / "collection"
    source = "https://example.com/course"
    resource = "https://example.com/paper.pdf"
    write(collection / "source_manifest.md", manifest(source, resource))
    write_entry_map(collection)
    write(
        collection / "01_Course.md",
        (
            "# Course\n\n"
            f"Source: {source}\n\n"
            f"Resource note: {resource}\n\n"
            "This note explains the reading list item with concrete mechanisms, limitations, and next checks.\n"
        ),
    )

    result = run_checker(collection, "--source", source, "--per-link-notes")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "web_note_issues 0" in result.stdout


@pytest.mark.parametrize(
    ("link_label", "include_resource_in_note", "expected_returncode"),
    [
        (r"Paper P(A \| B)", False, 1),
        (r"Paper P(A \| B)", True, 0),
        ("Paper P(A | B)", False, 1),
        ("Paper P(A | B)", True, 0),
    ],
    ids=("escaped-pipe-missing-note", "escaped-pipe-note-present", "plain-pipe-missing-note", "plain-pipe-note-present"),
)
def test_collector_manifest_round_trip_requires_each_learning_resource_note(
    tmp_path: Path,
    link_label: str,
    include_resource_in_note: bool,
    expected_returncode: int,
) -> None:
    collection = tmp_path / "collection"
    html_path = tmp_path / "course.html"
    resource = "https://example.com/paper.pdf"
    html_path.write_text(
        f"<!doctype html><title>Course</title><a href=\"{resource}\">{link_label}</a>",
        encoding="utf-8",
    )
    page = collect_sources([str(html_path)])[0]
    generated_manifest = build_manifest([page])
    write(collection / "source_manifest.md", generated_manifest)
    resource_rows = [
        row for row in load_manifest_rows(collection / "source_manifest.md")
        if row.section == "Learning Resources"
    ]
    assert len(resource_rows) == 1
    assert resource_rows[0].values["Title"] == link_label
    write_entry_map(collection)
    note_resource = f"\n\nSource: {resource}" if include_resource_in_note else ""
    write(
        collection / "01_Course.md",
        "# Course\n\nFinalized course-specific explanation." + note_resource + "\n",
    )

    result = run_checker(collection, "--per-link-notes")

    assert result.returncode == expected_returncode, result.stdout + result.stderr
    if include_resource_in_note:
        assert "web_note_issues 0" in result.stdout
    else:
        assert "MISSING_PER_LINK_NOTE" in result.stdout
        assert resource in result.stdout


@pytest.mark.parametrize(
    ("malformation", "expected_message"),
    [
        ("missing_pages_header", "Pages section is missing its table header"),
        ("missing_resources_header", "Learning Resources section is missing its table header"),
        ("duplicate_column", "duplicate column name"),
        ("malformed_row", "has 2 cells; expected 7"),
        ("missing_leading_pipe", "malformed Learning Resources table row is missing its leading"),
        ("missing_table_delimiters", "malformed Learning Resources table row is missing Markdown table delimiters"),
        ("empty_resource_url", "Learning Resources row has an empty URL"),
        ("invalid_resource_url_syntax", "Learning Resources URL has invalid syntax"),
        ("invalid_page_url_syntax", "Pages URL has invalid syntax"),
        ("empty_page_url", "Pages row has an empty Kind, Original Source, or URL"),
    ],
)
def test_check_web_notes_rejects_malformed_manifest_tables(
    tmp_path: Path,
    malformation: str,
    expected_message: str,
) -> None:
    collection = tmp_path / "collection"
    source = "https://example.com/readings"
    resource = "https://example.com/paper.pdf"
    manifest_text = manifest(source, resource)
    if malformation == "missing_pages_header":
        pages_table = (
            "## Pages\n\n"
            "| Kind | Title | Original Source | URL | Access | Status | Error | Description |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
            f"| course_page | Course | {source} | {source} | ok | ok |  | Course page |\n"
        )
        manifest_text = manifest_text.replace(pages_table, "## Pages\n\n")
    elif malformation == "missing_resources_header":
        manifest_text = manifest(source)
        resource_table = (
            "## Learning Resources\n\n"
            "| Kind | Title | URL | Access | Status | Error | Source Page |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n"
        )
        manifest_text = manifest_text.replace(resource_table, "## Learning Resources\n\n")
    elif malformation == "duplicate_column":
        manifest_text = manifest_text.replace(
            "| Kind | Title | URL | Access | Status | Error | Source Page |",
            "| Kind | URL | URL | Access | Status | Error | Source Page |",
        )
    elif malformation == "malformed_row":
        manifest_text += "| pdf | truncated row |\n"
    elif malformation == "missing_leading_pipe":
        manifest_text += f"pdf | Malformed row | {resource} | listed | listed |  | {source} |\n"
    elif malformation == "missing_table_delimiters":
        manifest_text += f"pdf Malformed row {resource} listed listed source {source}\n"
    elif malformation == "empty_resource_url":
        manifest_text = manifest(
            source,
            resources=[("", "listed", "listed", "")],
        )
    elif malformation == "invalid_resource_url_syntax":
        manifest_text = manifest(
            source,
            resources=[("http://[", "inaccessible", "skipped", "malformed source URL")],
        )
    elif malformation == "invalid_page_url_syntax":
        manifest_text = manifest(source).replace(
            f"| course_page | Course | {source} | {source} |",
            f"| course_page | Course | {source} | http://[ |",
        )
    elif malformation == "empty_page_url":
        manifest_text = manifest(source).replace(
            f"| course_page | Course | {source} | {source} |",
            f"| course_page | Course | {source} |  |",
        )
    write(collection / "source_manifest.md", manifest_text)
    write_entry_map(collection)
    write(collection / "01_Course.md", f"# Course\n\nSource-specific explanation: {source}\n")

    result = run_checker(collection, "--source", source, "--per-link-notes")

    assert result.returncode == 1
    assert "INVALID_MANIFEST" in result.stdout
    assert expected_message in result.stdout


def test_check_web_notes_accepts_legacy_minimal_manifest_headers(tmp_path: Path) -> None:
    collection = tmp_path / "collection"
    source = "https://example.com/readings"
    resource = "https://example.com/readings/chapter-1"
    write(
        collection / "source_manifest.md",
        "# Source Manifest\n\n"
        "## Pages\n\n"
        "| Kind | Original Source | URL |\n"
        "| --- | --- | --- |\n"
        f"| book_or_chapter | {source} | {source} |\n\n"
        "## Learning Resources\n\n"
        "| URL | Access | Status |\n"
        "| --- | --- | --- |\n"
        f"| {resource} | listed | listed |\n",
    )
    write_entry_map(collection)
    write(
        collection / "01_Chapter.md",
        f"# Chapter\n\nSource: {source}\n\nResource: {resource}\n\nFinished explanation.\n",
    )

    result = run_checker(collection, "--source", source, "--per-link-notes")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "web_note_issues 0" in result.stdout


def test_manifest_parser_preserves_windows_paths_regex_and_latex(tmp_path: Path) -> None:
    collection = tmp_path / "collection"
    source = r"C:\Course\index.html"
    write(collection / "source_manifest.md", manifest(source))
    rows_text = (collection / "source_manifest.md").read_text(encoding="utf-8")
    rows_text = rows_text.replace("Course page |", r"regex \d+ and latex \alpha |")
    write(collection / "source_manifest.md", rows_text)
    rows = load_manifest_rows(collection / "source_manifest.md")
    assert rows[0].values["Original Source"] == source
    assert rows[0].values["Description"] == r"regex \d+ and latex \alpha"
    write_entry_map(collection)
    write(collection / "01_Course.md", "# Course\n\nFinal explanation.\n")

    result = run_checker(collection, "--source", source)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "web_note_issues 0" in result.stdout


def test_check_web_notes_does_not_require_notes_for_provenance_helpers(tmp_path: Path):
    collection = tmp_path / "collection"
    source = "https://example.com/course"
    helper = "https://example.com/static/app.js"
    manifest_text = manifest(source) + (
        "\n## Provenance Helpers\n\n"
        "| Kind | Title | URL | Source Page |\n"
        "| --- | --- | --- | --- |\n"
        f"| web_page | Client bundle | {helper} | {source} |\n"
    )
    write(collection / "source_manifest.md", manifest_text)
    write_entry_map(collection)
    write(collection / "01_Course.md", f"# Course\n\nSource: {source}\n\nFinal explanation.\n")

    result = run_checker(collection, "--source", source, "--per-link-notes")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "web_note_issues 0" in result.stdout


def test_check_web_notes_direct_pdf_requires_finalized_map_and_detail_note(tmp_path: Path):
    collection = tmp_path / "collection"
    source = "https://example.com/papers/paper.pdf"
    write(collection / "source_manifest.md", manifest(source, page_kind="pdf", resources=[(source, "recorded", "recorded", "")]))

    incomplete = run_checker(collection, "--source", source)
    assert incomplete.returncode == 1
    assert "MISSING_ENTRY_MAP" in incomplete.stdout
    assert "MISSING_DETAIL_NOTE" in incomplete.stdout

    write_entry_map(collection)
    write(collection / "01_Course.md", f"# Course\n\nSource: {source}\n\nFinal source-specific explanation.\n")
    result = run_checker(collection, "--source", source)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "web_note_issues 0" in result.stdout


@pytest.mark.parametrize(
    "support_name",
    [
        "99_内容覆盖审查.md",
        "source_manifest_2.md",
        "source_coverage_audit.md",
        "validation_report.md",
    ],
)
def test_check_web_notes_support_artifact_does_not_satisfy_detail_contract(
    tmp_path: Path,
    support_name: str,
) -> None:
    collection = tmp_path / support_name.removesuffix(".md")
    source = "https://example.com/course"
    write(collection / "source_manifest.md", manifest(source))
    write_entry_map(collection)
    write(
        collection / support_name,
        f"# Validation support\n\n| source | status |\n|---|---|\n| {source} | covered |\n",
    )

    result = run_checker(collection, "--source", source)

    assert result.returncode == 1
    assert "MISSING_DETAIL_NOTE" in result.stdout


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("README.md", "# Collection README\n"),
        ("AGENT.md", "# Agent Instructions\n\nRun the validator.\n"),
        ("01_Empty.md", "# Empty Topic\n\n## Notes\n"),
    ],
)
def test_check_web_notes_shell_markdown_does_not_satisfy_detail_contract(
    tmp_path: Path,
    name: str,
    text: str,
) -> None:
    collection = tmp_path / name.removesuffix(".md")
    source = "https://example.com/course"
    write(collection / "source_manifest.md", manifest(source))
    write_entry_map(collection)
    write(collection / name, text)

    result = run_checker(collection, "--source", source)

    assert result.returncode == 1
    assert "MISSING_DETAIL_NOTE" in result.stdout


def test_check_web_notes_accepts_short_genuine_detail_note(tmp_path: Path) -> None:
    collection = tmp_path / "collection"
    source = "https://example.com/course"
    write(collection / "source_manifest.md", manifest(source))
    write_entry_map(collection)
    write(collection / "01_Topic.md", "# Topic\n\nUseful insight.\n")

    result = run_checker(collection, "--source", source)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "web_note_issues 0" in result.stdout


def test_check_web_notes_per_link_requires_genuine_detail_note(tmp_path: Path) -> None:
    collection = tmp_path / "collection"
    source = "https://example.com/course"
    resource = "https://example.com/paper.pdf"
    write(collection / "source_manifest.md", manifest(source, resource))
    write_entry_map(collection)
    write(collection / "README.md", f"# README\n\nResource: {resource}\n")

    result = run_checker(collection, "--source", source, "--per-link-notes")

    assert result.returncode == 1
    assert "MISSING_DETAIL_NOTE" in result.stdout
    assert "MISSING_PER_LINK_NOTE" in result.stdout


@pytest.mark.parametrize("entry_name", ["00_Course_Overview.md", "00 Course Overview.md"])
def test_check_web_notes_accepts_english_course_overview_entry_map(
    tmp_path: Path,
    entry_name: str,
) -> None:
    collection = tmp_path / entry_name.removesuffix(".md")
    source = "https://example.com/course"
    write(collection / "source_manifest.md", manifest(source))
    write(collection / entry_name, "# Course Overview\n\n[[01_Topic]]\n")
    write(collection / "01_Topic.md", "# Topic\n\nUseful insight.\n")

    result = run_checker(collection, "--source", source)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "web_note_issues 0" in result.stdout


def test_check_web_notes_fails_when_reading_list_resource_has_no_note(tmp_path: Path):
    collection = tmp_path / "collection"
    source = "https://example.com/readings"
    chapter_1 = "https://example.com/readings/chapter-1"
    chapter_2 = "https://example.com/readings/chapter-2"
    write(
        collection / "source_manifest.md",
        manifest(
            source,
            page_kind="book_or_chapter",
            resources=[(chapter_1, "listed", "listed", ""), (chapter_2, "listed", "listed", "")],
        ),
    )
    write_entry_map(collection)
    write(collection / "01_Chapter_1.md", f"# Chapter 1\n\nSource: {chapter_1}\n\nFinished source-specific note.\n")

    result = run_checker(collection, "--source", source, "--per-link-notes")

    assert result.returncode == 1
    assert "MISSING_PER_LINK_NOTE" in result.stdout
    assert chapter_2 in result.stdout


def test_per_link_notes_rejects_one_aggregator_for_multiple_resources(
    tmp_path: Path,
) -> None:
    collection = tmp_path / "collection"
    source = "https://example.com/readings"
    chapter_1 = "https://example.com/readings/chapter-1"
    chapter_2 = "https://example.com/readings/chapter-2"
    write(
        collection / "source_manifest.md",
        manifest(
            source,
            page_kind="book_or_chapter",
            resources=[
                (chapter_1, "listed", "listed", ""),
                (chapter_2, "listed", "listed", ""),
            ],
        ),
    )
    write_entry_map(collection)
    write(
        collection / "01_Aggregate.md",
        f"# Aggregate\n\n{chapter_1}\n\n{chapter_2}\n\nCombined explanation.\n",
    )

    aggregated = run_checker(collection, "--source", source, "--per-link-notes")
    assert aggregated.returncode == 1
    assert aggregated.stdout.count("MISSING_PER_LINK_NOTE") == 1

    write(
        collection / "02_Chapter_2.md",
        f"# Chapter 2\n\n{chapter_2}\n\nIndependent explanation.\n",
    )
    separated = run_checker(collection, "--source", source, "--per-link-notes")
    assert separated.returncode == 0, separated.stdout + separated.stderr


def test_check_web_notes_skipped_or_inaccessible_resource_does_not_require_note(tmp_path: Path):
    collection = tmp_path / "collection"
    source = "https://example.com/readings"
    chapter_1 = "https://example.com/readings/chapter-1"
    chapter_2 = "https://example.com/readings/chapter-2"
    write(
        collection / "source_manifest.md",
        manifest(
            source,
            page_kind="book_or_chapter",
            resources=[
                (chapter_1, "listed", "listed", ""),
                (chapter_2, "inaccessible", "skipped", "HTTP 403"),
            ],
        ),
    )
    write_entry_map(collection)
    write(collection / "01_Chapter_1.md", f"# Chapter 1\n\nSource: {chapter_1}\n\nFinished source-specific note.\n")

    result = run_checker(collection, "--source", source, "--per-link-notes")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "web_note_issues 0" in result.stdout


def test_collector_generated_inaccessible_resource_error_keeps_explicit_exemption(tmp_path: Path) -> None:
    collection = tmp_path / "collection"
    missing_pdf = tmp_path / "missing-paper.pdf"
    page = collect_sources([str(missing_pdf)])[0]
    generated_manifest = build_manifest([page])
    assert page.access_status == "inaccessible"
    assert page.error
    write(collection / "source_manifest.md", generated_manifest)
    write_entry_map(collection)
    write(collection / "01_Paper.md", "# Paper\n\nFinished source-specific explanation.\n")

    result = run_checker(collection, "--source", str(missing_pdf), "--per-link-notes")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "web_note_issues 0" in result.stdout


def test_arbitrary_resource_error_text_does_not_exempt_missing_note(tmp_path: Path) -> None:
    collection = tmp_path / "collection"
    source = "https://example.com/readings"
    chapter_1 = "https://example.com/readings/chapter-1"
    chapter_2 = "https://example.com/readings/chapter-2"
    write(
        collection / "source_manifest.md",
        manifest(
            source,
            page_kind="book_or_chapter",
            resources=[
                (chapter_1, "listed", "listed", ""),
                (chapter_2, "listed", "listed", "no chapter note yet"),
            ],
        ),
    )
    write_entry_map(collection)
    write(collection / "01_Chapter_1.md", f"# Chapter 1\n\nSource: {chapter_1}\n\nFinished explanation.\n")

    result = run_checker(collection, "--source", source, "--per-link-notes")

    assert result.returncode == 1
    assert "MISSING_PER_LINK_NOTE" in result.stdout
    assert chapter_2 in result.stdout


@pytest.mark.parametrize(
    ("access", "status"),
    [("listed", "inaccessible"), ("inaccessible", "listed"), ("ok", "failed"), ("http_403", "ok")],
)
def test_check_web_notes_rejects_contradictory_resource_states(
    tmp_path: Path,
    access: str,
    status: str,
) -> None:
    collection = tmp_path / "collection"
    source = "https://example.com/readings"
    resource = "https://example.com/readings/chapter-1"
    write(
        collection / "source_manifest.md",
        manifest(
            source,
            page_kind="book_or_chapter",
            resources=[(resource, access, status, "HTTP 403")],
        ),
    )
    write_entry_map(collection)
    write(collection / "01_Chapter_1.md", f"# Chapter 1\n\nSource: {resource}\n\nFinished explanation.\n")

    result = run_checker(collection, "--source", source)

    assert result.returncode == 1
    assert "CONTRADICTORY_RESOURCE_STATUS" in result.stdout
    assert resource in result.stdout


def test_check_web_notes_rejects_external_manifest_symlink(tmp_path: Path) -> None:
    collection = tmp_path / "collection"
    collection.mkdir()
    source = "https://example.com/course"
    outside_manifest = tmp_path / "outside_manifest.md"
    write(outside_manifest, manifest(source))
    (collection / "source_manifest.md").symlink_to(outside_manifest)
    write_entry_map(collection)
    write(collection / "01_Course.md", f"# Course\n\nSource: {source}\n\nFinished note.\n")

    result = run_checker(collection, "--source", source)

    assert result.returncode == 1
    assert "UNSAFE_SYMLINK" in result.stdout
    assert "INVALID_MANIFEST" in result.stdout


def test_check_web_notes_rejects_external_per_link_note_symlink(tmp_path: Path) -> None:
    collection = tmp_path / "collection"
    source = "https://example.com/course"
    resource = "https://example.com/paper.pdf"
    write(collection / "source_manifest.md", manifest(source, resource))
    write_entry_map(collection)
    write(collection / "01_Course.md", f"# Course\n\nSource: {source}\n\nFinished note.\n")
    outside_note = tmp_path / "outside_note.md"
    write(outside_note, f"# External\n\nResource: {resource}\n")
    (collection / "02_External.md").symlink_to(outside_note)

    result = run_checker(collection, "--source", source, "--per-link-notes")

    assert result.returncode == 1
    assert "UNSAFE_SYMLINK" in result.stdout
    assert "MISSING_PER_LINK_NOTE" in result.stdout


@pytest.mark.parametrize(
    "kind",
    ("leaf_same_inode", "leaf_external", "ancestor", "broken_leaf", "broken_ancestor"),
)
def test_check_web_notes_rejects_symlinked_collection_root_components(
    tmp_path: Path,
    kind: str,
) -> None:
    source = "https://example.com/course"
    real_collection = tmp_path / "real" / "collection"
    if not kind.startswith("broken"):
        write(real_collection / "source_manifest.md", manifest(source))
        write_entry_map(real_collection)
        write(real_collection / "01_Course.md", "# Course\n\nFinished source-specific note.\n")

    if kind in {"leaf_same_inode", "leaf_external"}:
        alias_parent = tmp_path / ("real" if kind == "leaf_same_inode" else "boundary")
        alias_parent.mkdir(parents=True, exist_ok=True)
        root = alias_parent / "collection-alias"
        root.symlink_to(real_collection, target_is_directory=True)
        assert root.stat().st_ino == real_collection.stat().st_ino
    elif kind == "ancestor":
        alias_parent = tmp_path / "parent-alias"
        alias_parent.symlink_to(real_collection.parent, target_is_directory=True)
        root = alias_parent / real_collection.name
        assert root.stat().st_ino == real_collection.stat().st_ino
    elif kind == "broken_leaf":
        root = tmp_path / "broken-collection"
        root.symlink_to(tmp_path / "missing-collection", target_is_directory=True)
    else:
        alias_parent = tmp_path / "broken-parent"
        alias_parent.symlink_to(tmp_path / "missing-parent", target_is_directory=True)
        root = alias_parent / "collection"

    result = run_checker(root, "--source", source)

    assert result.returncode == 1
    assert "UNSAFE_SYMLINK" in result.stdout


@pytest.mark.parametrize(
    "hidden_note",
    [
        "# Hidden\n\n<!--\n{resource}\n-->\n",
        "# Hidden\n\n%%\n{resource}\n%%\n",
        "# Hidden\n\n<!-- outer\n%%\n{resource}\n%%\n-->\n",
        "# Hidden\n\n%% outer\n<!--\n{resource}\n-->\n%%\n",
        "# Hidden\n\n```text\n{resource}\n````\n",
        "# Hidden\n\n~~~text\n{resource}\n~~~~\n",
        "# Hidden\n\n`{resource}`\n",
        "# Hidden\n\n    {resource}\n",
        "# Hidden\n\n> ```text\n> {resource}\n> ```\n",
        "# Hidden\n\n- ```text\n  {resource}\n  ```\n",
    ],
    ids=(
        "html-comment",
        "obsidian-comment",
        "html-outer-nested",
        "obsidian-outer-nested",
        "backtick-fence",
        "tilde-fence",
        "inline-code",
        "indented-code",
        "blockquote-fence",
        "list-fence",
    ),
)
def test_hidden_or_code_url_cannot_satisfy_detail_or_per_link_contract(
    tmp_path: Path,
    hidden_note: str,
) -> None:
    collection = tmp_path / "collection"
    source = "https://example.com/readings"
    resource = "https://example.com/paper.pdf"
    write(collection / "source_manifest.md", manifest(source, resource))
    write_entry_map(collection)
    write(collection / "01_Hidden.md", hidden_note.format(resource=resource))

    result = run_checker(collection, "--source", source, "--per-link-notes")

    assert result.returncode == 1
    assert "MISSING_DETAIL_NOTE" in result.stdout
    assert "MISSING_PER_LINK_NOTE" in result.stdout


def test_visible_url_after_nested_hidden_contexts_satisfies_per_link_contract(
    tmp_path: Path,
) -> None:
    collection = tmp_path / "collection"
    source = "https://example.com/readings"
    resource = "https://example.com/paper.pdf"
    write(collection / "source_manifest.md", manifest(source, resource))
    write_entry_map(collection)
    write(
        collection / "01_Visible.md",
        "# Visible\n\n"
        "<!-- hidden copy: {resource} -->\n\n"
        "- example\n"
        "  ```text\n"
        "  {resource}\n"
        "  ```\n\n"
        "Concrete mechanism and limitation.\n\n"
        "Visible source: {resource}\n".format(resource=resource),
    )

    result = run_checker(collection, "--source", source, "--per-link-notes")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "web_note_issues 0" in result.stdout


def test_per_link_coverage_requires_exact_extracted_url_token(tmp_path: Path) -> None:
    collection = tmp_path / "collection"
    source = "https://example.com/readings"
    resource = "https://example.com/paper.pdf"
    write(collection / "source_manifest.md", manifest(source, resource))
    write_entry_map(collection)
    write(
        collection / "01_Course.md",
        f"# Course\n\nSource: {source}\n\nWrong resource: {resource}.backup\n",
    )

    result = run_checker(collection, "--source", source, "--per-link-notes")

    assert result.returncode == 1
    assert "MISSING_PER_LINK_NOTE" in result.stdout


def test_per_link_url_identity_preserves_reserved_percent_octets(tmp_path: Path) -> None:
    collection = tmp_path / "collection"
    source = "https://example.com/readings"
    resource = "https://example.com/a%2Fb?next=a%26b%3Dc"
    write(collection / "source_manifest.md", manifest(source, resource))
    write_entry_map(collection)
    note = collection / "01_Course.md"
    write(note, f"# Course\n\nSource: {source}\n\nDecoded lookalike: https://example.com/a/b?next=a&b=c\n")

    mismatch = run_checker(collection, "--source", source, "--per-link-notes")
    assert mismatch.returncode == 1
    assert "MISSING_PER_LINK_NOTE" in mismatch.stdout

    write(note, f"# Course\n\nSource: {source}\n\nExact resource: https://example.com/a%2fb?next=a%26b%3dc\n")
    match = run_checker(collection, "--source", source, "--per-link-notes")
    assert match.returncode == 0, match.stdout + match.stderr


def test_per_link_url_extraction_handles_visible_table_delimiters(tmp_path: Path) -> None:
    collection = tmp_path / "collection"
    source = "https://example.com/readings"
    resource = "https://example.com/paper.pdf"
    write(collection / "source_manifest.md", manifest(source, resource))
    write_entry_map(collection)
    write(
        collection / "01_Course.md",
        f"# Course\n\nSource: {source}\n\n| resource |\n| --- |\n| {resource} |\n",
    )

    result = run_checker(collection, "--source", source, "--per-link-notes")

    assert result.returncode == 0, result.stdout + result.stderr
