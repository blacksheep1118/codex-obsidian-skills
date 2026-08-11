from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unicodedata
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "extract_presentation_text.py"
sys.path.insert(0, str(ROOT))

from scripts import extract_presentation_text  # noqa: E402
from scripts.extract_presentation_text import allocate_output_paths  # noqa: E402


def write_minimal_pptx(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "ppt/slides/slide1.xml",
            f'<a:t xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">{text}</a:t>',
        )


def run_extractor(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def test_extract_presentation_text_keeps_unique_basename(tmp_path: Path) -> None:
    source = tmp_path / "source" / "lecture.pptx"
    output_dir = tmp_path / "out"
    write_minimal_pptx(source, "Unique source")

    result = run_extractor(str(source), "--output-dir", str(output_dir))

    assert result.returncode == 0, result.stdout + result.stderr
    output_text = (output_dir / "lecture.txt").read_text(encoding="utf-8")
    assert output_text.strip().endswith("Unique source")
    assert "EXTRACTION METADATA (NOT SOURCE TEXT)" in output_text
    assert "Coverage: partial text hints only" in output_text
    assert "Visual/OCR coverage: none" in output_text
    assert "Speaker notes coverage: not extracted by this PPTX fallback" in output_text
    metadata, extracted_body = output_text.split("=== EXTRACTED TEXT HINTS ===\n", 1)
    assert "EXTRACTION METADATA" in metadata
    assert "EXTRACTION METADATA" not in extracted_body
    assert extracted_body.strip().endswith("Unique source")
    assert f"source={source}" in result.stdout


def test_legacy_extraction_metadata_marks_unreliable_speaker_note_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = Path("lecture.ppt")
    monkeypatch.setattr(extract_presentation_text, "extract", lambda path: "Legacy source text\n")

    output_text = extract_presentation_text.render_extraction(source)

    metadata, extracted_body = output_text.split("=== EXTRACTED TEXT HINTS ===\n", 1)
    assert "Backend: legacy-ppt-ole-cfb-text-records" in metadata
    assert "Coverage: partial text hints only" in metadata
    assert "Visual/OCR coverage: none" in metadata
    assert "Speaker notes coverage: not reliably distinguished or covered" in metadata
    assert extracted_body == "Legacy source text\n"


def test_extract_presentation_text_disambiguates_same_basename_sources(tmp_path: Path) -> None:
    first = tmp_path / "course-a" / "lecture.pptx"
    second = tmp_path / "course-b" / "lecture.pptx"
    output_dir = tmp_path / "out"
    write_minimal_pptx(first, "Course A evidence")
    write_minimal_pptx(second, "Course B evidence")

    result = run_extractor(str(first), str(second), "--output-dir", str(output_dir))

    assert result.returncode == 0, result.stdout + result.stderr
    outputs = sorted(output_dir.glob("lecture--*.txt"))
    assert len(outputs) == 2
    assert len({path.name.casefold() for path in outputs}) == 2
    assert {path.read_text(encoding="utf-8").strip().splitlines()[-1] for path in outputs} == {
        "Course A evidence",
        "Course B evidence",
    }
    assert f"source={first}" in result.stdout
    assert f"source={second}" in result.stdout


def test_allocate_output_paths_disambiguates_canonical_unicode_collisions_in_any_order(
    tmp_path: Path,
) -> None:
    first = tmp_path / "course-a" / "é.pptx"
    second = tmp_path / "course-b" / "e\N{COMBINING ACUTE ACCENT}.pptx"
    expected_by_source: dict[Path, str] | None = None

    for sources in ([first, second], [second, first]):
        allocated = allocate_output_paths(sources, tmp_path / "out")
        normalized_names = {
            unicodedata.normalize("NFC", path.name).casefold()
            for path in allocated
        }
        by_source = dict(zip(sources, (path.name for path in allocated)))

        assert len(normalized_names) == 2
        if expected_by_source is None:
            expected_by_source = by_source
        else:
            assert by_source == expected_by_source


@pytest.mark.parametrize("dangling", [False, True])
def test_extract_presentation_text_rejects_unique_output_symlink(
    tmp_path: Path,
    dangling: bool,
) -> None:
    source = tmp_path / "source" / "lecture.pptx"
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    write_minimal_pptx(source, "Unique source")
    outside = tmp_path / "outside.txt"
    if not dangling:
        outside.write_text("external", encoding="utf-8")
    (output_dir / "lecture.txt").symlink_to(outside)

    result = run_extractor(str(source), "--output-dir", str(output_dir))

    assert result.returncode == 1
    assert "symlink" in result.stderr.lower()
    assert not outside.exists() if dangling else outside.read_text(encoding="utf-8") == "external"


@pytest.mark.parametrize("dangling", [False, True])
def test_extract_presentation_text_rejects_collision_hash_output_symlink(
    tmp_path: Path,
    dangling: bool,
) -> None:
    first = tmp_path / "course-a" / "lecture.pptx"
    second = tmp_path / "course-b" / "lecture.pptx"
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    write_minimal_pptx(first, "Course A evidence")
    write_minimal_pptx(second, "Course B evidence")
    target = allocate_output_paths([first, second], output_dir)[0]
    outside = tmp_path / "outside.txt"
    if not dangling:
        outside.write_text("external", encoding="utf-8")
    target.symlink_to(outside)

    result = run_extractor(str(first), str(second), "--output-dir", str(output_dir))

    assert result.returncode == 1
    assert "symlink" in result.stderr.lower()
    assert not outside.exists() if dangling else outside.read_text(encoding="utf-8") == "external"


def test_extract_presentation_text_replaces_hardlink_entry_without_mutating_external_inode(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source" / "lecture.pptx"
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    write_minimal_pptx(source, "Unique source")
    outside = tmp_path / "outside.txt"
    outside.write_text("external", encoding="utf-8")
    output = output_dir / "lecture.txt"
    os.link(outside, output)

    result = run_extractor(str(source), "--output-dir", str(output_dir))

    assert result.returncode == 0, result.stdout + result.stderr
    assert outside.read_text(encoding="utf-8") == "external"
    assert output.read_text(encoding="utf-8").strip().endswith("Unique source")
    assert output.stat().st_ino != outside.stat().st_ino
