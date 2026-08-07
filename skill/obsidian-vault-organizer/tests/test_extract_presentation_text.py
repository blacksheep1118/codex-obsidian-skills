from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "extract_presentation_text.py"
sys.path.insert(0, str(ROOT))

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
    assert (output_dir / "lecture.txt").read_text(encoding="utf-8").strip().endswith("Unique source")
    assert f"source={source}" in result.stdout


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
