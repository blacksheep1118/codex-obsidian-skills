from pathlib import Path
import struct
import subprocess
import sys
from zipfile import ZipFile

import pytest

from scripts.extract_pptx_text import (
    PptxExtractionError,
    extract_pptx,
    extract_pptx_result,
    extract_pptx_with_zip_result,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "extract_pptx_text.py"
PIPELINE_SCRIPT = ROOT / "scripts" / "ppt_to_obsidian_pipeline.py"


def write_required_package(
    path: Path,
    *,
    content_types: bytes = b"<Types/>",
    presentation: bytes = b"<presentation/>",
) -> None:
    with ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("ppt/presentation.xml", presentation)


def set_encrypted_flags(path: Path) -> None:
    """Mark every member encrypted without needing an encryption writer."""

    payload = bytearray(path.read_bytes())
    for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        offset = 0
        while (offset := payload.find(signature, offset)) >= 0:
            flags = struct.unpack_from("<H", payload, offset + flag_offset)[0]
            struct.pack_into("<H", payload, offset + flag_offset, flags | 0x1)
            offset += len(signature)
    path.write_bytes(payload)


def run_extractor(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def test_extract_pptx_sample_contains_ordered_slide_text():
    sample = Path("examples/sample-course/raw/sample_course.pptx")
    output = extract_pptx(sample)

    assert "# Extracted PPTX Text: sample_course.pptx" in output
    assert "## Slide 1: 机器学习导论" in output
    assert "- 经验风险与泛化" in output
    assert "- 知识点精简复习版_含公式.md" in output
    assert "- Backend: `python-pptx`" in output
    assert "- Slides:" in output


def test_extract_pptx_sample_keeps_python_backend_without_fallback() -> None:
    sample = Path("examples/sample-course/raw/sample_course.pptx")

    result = extract_pptx_result(sample)

    assert result.backend == "python-pptx"
    assert result.partial is False


@pytest.mark.parametrize(
    ("fixture", "reason"),
    [
        ("missing", "file does not exist"),
        ("directory", "input is not a regular file"),
        ("non-zip", "invalid PPTX ZIP package"),
        ("truncated", "invalid PPTX ZIP package"),
        ("encrypted", "encrypted PPTX packages are not supported"),
        ("missing-ooxml", "PPTX package is missing required OOXML parts"),
        ("invalid-ooxml", "PPTX package contains malformed required XML"),
    ],
)
def test_extract_pptx_cli_reports_stable_errors_without_tracebacks(
    tmp_path: Path,
    fixture: str,
    reason: str,
) -> None:
    source = tmp_path / f"{fixture}.pptx"
    if fixture == "directory":
        source.mkdir()
    elif fixture == "non-zip":
        source.write_bytes(b"not-a-zip")
    elif fixture == "truncated":
        write_required_package(source)
        source.write_bytes(source.read_bytes()[:-10])
    elif fixture == "encrypted":
        write_required_package(source)
        set_encrypted_flags(source)
    elif fixture == "missing-ooxml":
        with ZipFile(source, "w") as archive:
            archive.writestr("ppt/presentation.xml", "<presentation/>")
    elif fixture == "invalid-ooxml":
        write_required_package(source, content_types=b"<Types>")

    result = run_extractor(source)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == f"ERROR: {source}: {reason}\n"
    assert "Traceback" not in result.stderr


def test_pipeline_reuses_structured_pptx_error_boundary(tmp_path: Path) -> None:
    source = tmp_path / "broken.pptx"
    source.write_bytes(b"not-a-zip")

    result = subprocess.run(
        [
            sys.executable,
            str(PIPELINE_SCRIPT),
            str(source),
            "--output-dir",
            str(tmp_path / "out"),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == f"ERROR: {source}: invalid PPTX ZIP package\n"
    assert "Traceback" not in result.stderr


def test_shared_pptx_entry_hides_internal_exception_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pptx

    sample = Path("examples/sample-course/raw/sample_course.pptx")

    def fail_parse(_path: str):
        raise RuntimeError("SENSITIVE_INTERNAL_DETAIL")

    monkeypatch.setattr(pptx, "Presentation", fail_parse)

    with pytest.raises(PptxExtractionError) as caught:
        extract_pptx_result(sample)

    assert str(caught.value) == f"{sample}: PPTX package could not be parsed"
    assert "SENSITIVE_INTERNAL_DETAIL" not in str(caught.value)


@pytest.mark.parametrize(
    "signal",
    [KeyboardInterrupt(), SystemExit(7)],
    ids=("keyboard-interrupt", "system-exit"),
)
def test_shared_pptx_entry_does_not_hide_control_flow_exceptions(
    monkeypatch: pytest.MonkeyPatch,
    signal: BaseException,
) -> None:
    import pptx

    sample = Path("examples/sample-course/raw/sample_course.pptx")

    def stop_parse(_path: str):
        raise signal

    monkeypatch.setattr(pptx, "Presentation", stop_parse)

    with pytest.raises(type(signal)):
        extract_pptx_result(sample)


def test_zip_fallback_reports_backend_partial_and_slide_media_stats(tmp_path: Path):
    source = tmp_path / "fallback.pptx"
    text_slide = (
        '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        "<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Visible text</a:t></a:r></a:p>"
        "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
    )
    media_only_slide = (
        '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        "<p:cSld><p:spTree><p:pic /></p:spTree></p:cSld></p:sld>"
    )
    with ZipFile(source, "w") as archive:
        archive.writestr("ppt/slides/slide1.xml", text_slide)
        archive.writestr("ppt/slides/slide2.xml", media_only_slide)

    result = extract_pptx_with_zip_result(source)

    assert result.backend == "zip-xml-fallback"
    assert result.partial is True
    assert result.slide_count == 2
    assert result.blank_slides == 1
    assert result.media_objects == 1
    assert "- Partial fallback: true" in result.markdown
    assert "Use OCR or manual slide inspection" in result.markdown
