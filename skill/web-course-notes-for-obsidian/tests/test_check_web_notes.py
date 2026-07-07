from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_web_notes.py"


def run_checker(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    write(
        collection / "01_Course.md",
        "---\nstatus: scaffold\n---\n\n# Course\n\n- 待补充: source details.\n",
    )

    result = run_checker(collection, "--source", source, "--source", "https://example.com/missing")

    assert result.returncode == 1
    assert "SCAFFOLD_RESIDUE" in result.stdout
    assert "MISSING_USER_SOURCE" in result.stdout


def test_check_web_notes_passes_finalized_note_and_per_link_resource(tmp_path: Path):
    collection = tmp_path / "collection"
    source = "https://example.com/course"
    resource = "https://example.com/paper.pdf"
    write(collection / "source_manifest.md", manifest(source, resource))
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


def test_check_web_notes_direct_pdf_manifest_passes_source_coverage(tmp_path: Path):
    collection = tmp_path / "collection"
    source = "https://example.com/papers/paper.pdf"
    write(collection / "source_manifest.md", manifest(source, page_kind="pdf", resources=[(source, "recorded", "recorded", "")]))

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
    write(collection / "01_Chapter_1.md", f"# Chapter 1\n\nSource: {chapter_1}\n\nFinished source-specific note.\n")

    result = run_checker(collection, "--source", source, "--per-link-notes")

    assert result.returncode == 1
    assert "MISSING_PER_LINK_NOTE" in result.stdout
    assert chapter_2 in result.stdout


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
    write(collection / "01_Chapter_1.md", f"# Chapter 1\n\nSource: {chapter_1}\n\nFinished source-specific note.\n")

    result = run_checker(collection, "--source", source, "--per-link-notes")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "web_note_issues 0" in result.stdout
