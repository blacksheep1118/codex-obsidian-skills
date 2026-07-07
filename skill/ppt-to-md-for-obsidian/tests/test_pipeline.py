from pathlib import Path

from scripts.check_obsidian_links import check_links
from scripts.extract_pdf_text import LOW_COVERAGE_WARNING, PdfExtractionResult
from scripts.extract_legacy_ppt_text import LegacyPptTextResult
from scripts.ppt_to_obsidian_pipeline import PipelineConfig, run
import scripts.ppt_to_obsidian_pipeline as pipeline


def test_pipeline_extracts_cleans_and_writes_manifest(tmp_path: Path):
    config = PipelineConfig(
        source=Path("examples/sample-course/raw/sample_course.pptx"),
        output_dir=tmp_path / "out",
        mode="course-notes",
        unicode_math=True,
        course_name="示例课程",
    )

    processed = run(config)

    assert len(processed) == 1
    assert (config.output_dir / "raw_extracted" / "sample_course.md").exists()
    assert (config.output_dir / "cleaned" / "sample_course.md").exists()
    assert (config.output_dir / "pipeline_manifest.md").exists()
    assert (config.output_dir / "notes_skeleton" / "00_课程总览.md").exists()

    broken, self_links, checked = check_links(config.output_dir / "notes_skeleton")
    assert checked == 2
    assert broken == []
    assert self_links == []


def test_pipeline_uses_legacy_ppt_fallback_when_libreoffice_conversion_fails(monkeypatch, tmp_path: Path):
    source = tmp_path / "legacy.ppt"
    source.write_bytes(b"legacy ppt placeholder")

    def fail_conversion(path: Path, converted_dir: Path, soffice: str | None) -> Path:
        raise RuntimeError("LibreOffice unavailable")

    def fake_fallback(path: Path) -> LegacyPptTextResult:
        return LegacyPptTextResult(
            source=path,
            text="Legacy lecture title\nImportant bullet",
            text_record_count=2,
        )

    monkeypatch.setattr(pipeline, "convert_legacy_ppt", fail_conversion)
    monkeypatch.setattr(pipeline, "extract_legacy_ppt_text", fake_fallback)

    config = PipelineConfig(source=source, output_dir=tmp_path / "out")
    processed = run(config)

    assert len(processed) == 1
    assert processed[0].backend == "legacy-ppt-ole-cfb-fallback"
    assert processed[0].partial is True
    assert processed[0].text_record_count == 2

    raw = (config.output_dir / "raw_extracted" / "legacy.md").read_text(encoding="utf-8")
    manifest = (config.output_dir / "pipeline_manifest.md").read_text(encoding="utf-8")

    assert "Legacy PPT Text Fallback: legacy.ppt" in raw
    assert "Legacy lecture title" in raw
    assert "Extraction backend: `legacy-ppt-ole-cfb-fallback`" in manifest
    assert "Coverage: partial/fallback extraction" in manifest
    assert "Text records: 2" in manifest


def test_pipeline_marks_low_coverage_pdf_in_manifest(monkeypatch, tmp_path: Path):
    source = tmp_path / "scanned.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    def fake_extract_pdf_result(path: Path) -> PdfExtractionResult:
        return PdfExtractionResult(
            markdown=(
                "# Extracted PDF Text: scanned.pdf\n\n"
                f"{LOW_COVERAGE_WARNING}\n\n"
                "- Backend: `pypdf`\n"
                "- Pages: 2\n"
                "- Empty text pages: 2\n"
                "- Text characters: 0\n"
                "- Low coverage: true\n"
            ),
            backend="pypdf",
            low_coverage=True,
            empty_pages=2,
            char_count=0,
            page_count=2,
        )

    monkeypatch.setattr(pipeline, "extract_pdf_result", fake_extract_pdf_result)

    config = PipelineConfig(source=source, output_dir=tmp_path / "out")
    processed = run(config)

    assert len(processed) == 1
    assert processed[0].backend == "pdf:pypdf"
    assert processed[0].low_coverage is True
    assert processed[0].empty_pages == 2
    assert processed[0].char_count == 0

    raw = (config.output_dir / "raw_extracted" / "scanned.md").read_text(encoding="utf-8")
    manifest = (config.output_dir / "pipeline_manifest.md").read_text(encoding="utf-8")

    assert LOW_COVERAGE_WARNING in raw
    assert "PDF pages: 2; empty text pages: 2; text characters: 0" in manifest
    assert "Coverage: low text coverage; do not claim complete source coverage without OCR/manual inspection." in manifest
