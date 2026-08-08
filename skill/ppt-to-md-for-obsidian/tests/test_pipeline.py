from pathlib import Path

import pytest

from scripts.check_obsidian_links import check_links
from scripts.extract_pdf_text import LOW_COVERAGE_WARNING, PdfExtractionResult
from scripts.extract_legacy_ppt_text import LegacyPptTextResult
from scripts.extract_pptx_text import PptxExtractionResult
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


def test_pipeline_manifest_records_pptx_fallback_stats_and_review_guidance(monkeypatch, tmp_path: Path):
    source = tmp_path / "media-heavy.pptx"
    source.write_bytes(b"placeholder")

    def fake_extract(path: Path) -> PptxExtractionResult:
        return PptxExtractionResult(
            markdown="# Extracted PPTX Text\n",
            backend="zip-xml-fallback",
            partial=True,
            slide_count=4,
            blank_slides=2,
            media_objects=3,
        )

    monkeypatch.setattr(pipeline, "extract_pptx_result", fake_extract)
    config = PipelineConfig(source=source, output_dir=tmp_path / "out")

    processed = run(config)
    manifest = (config.output_dir / "pipeline_manifest.md").read_text(encoding="utf-8")

    assert processed[0].backend == "pptx:zip-xml-fallback"
    assert processed[0].partial is True
    assert "PPTX slides: 4; slides without visible text: 2; media objects: 3" in manifest
    assert "OCR or manual slide inspection" in manifest
    assert "Coverage: partial/fallback extraction" in manifest


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


def test_pipeline_disambiguates_same_named_sources(monkeypatch, tmp_path: Path):
    first = tmp_path / "a" / "lecture.pdf"
    second = tmp_path / "b" / "lecture.pdf"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"%PDF-1.4\n")
    second.write_bytes(b"%PDF-1.4\n")

    def fake_extract_pdf_result(path: Path) -> PdfExtractionResult:
        return PdfExtractionResult(
            markdown=f"# Extracted PDF Text: {path.name}\n\ncontent for {path.parent.name}\n",
            backend="pypdf",
            low_coverage=False,
            empty_pages=0,
            char_count=10,
            page_count=1,
        )

    monkeypatch.setattr(pipeline, "extract_pdf_result", fake_extract_pdf_result)
    config = PipelineConfig(source=tmp_path, output_dir=tmp_path / "out")
    processed = run(config)

    assert len(processed) == 2
    raw_stems = {item.raw.stem for item in processed}
    cleaned_stems = {item.cleaned.stem for item in processed}
    assert len(raw_stems) == 2
    assert raw_stems == cleaned_stems
    assert "lecture" in raw_stems
    assert any(stem.startswith("lecture-") for stem in raw_stems)


@pytest.mark.parametrize("directory_name", ["raw_extracted", "cleaned", "notes_skeleton", "converted_pptx"])
def test_pipeline_rejects_symlinked_generated_directories(tmp_path: Path, directory_name: str) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (output_dir / directory_name).symlink_to(outside, target_is_directory=True)
    config = PipelineConfig(
        source=Path("examples/sample-course/raw/sample_course.pptx"),
        output_dir=output_dir,
    )

    with pytest.raises(ValueError, match="symlink"):
        run(config)

    assert list(outside.iterdir()) == []


@pytest.mark.parametrize(
    "relative_path",
    [
        "pipeline_manifest.md",
        "notes_skeleton/00_课程总览.md",
        "notes_skeleton/知识点详细版_含公式.md",
        "raw_extracted/sample_course.md",
        "cleaned/sample_course.md",
    ],
)
@pytest.mark.parametrize("dangling", [False, True])
def test_pipeline_rejects_existing_and_dangling_output_symlinks(
    tmp_path: Path,
    relative_path: str,
    dangling: bool,
) -> None:
    output_dir = tmp_path / "out"
    target = output_dir / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside.md"
    if not dangling:
        outside.write_text("external content", encoding="utf-8")
    target.symlink_to(outside)
    config = PipelineConfig(
        source=Path("examples/sample-course/raw/sample_course.pptx"),
        output_dir=output_dir,
    )

    with pytest.raises(ValueError, match="symlink"):
        run(config)

    if dangling:
        assert not outside.exists()
    else:
        assert outside.read_text(encoding="utf-8") == "external content"


@pytest.mark.parametrize("field", ["converted_dir", "overview_name"])
@pytest.mark.parametrize("unsafe", ["../escape", "/absolute/escape"])
def test_pipeline_rejects_unsafe_configured_child_paths(
    tmp_path: Path,
    field: str,
    unsafe: str,
) -> None:
    config = PipelineConfig(
        source=Path("examples/sample-course/raw/sample_course.pptx"),
        output_dir=tmp_path / "out",
    )
    setattr(config, field, unsafe)

    with pytest.raises(ValueError, match=field):
        run(config)


def test_pipeline_supports_safe_nested_configured_child_paths(tmp_path: Path) -> None:
    config = PipelineConfig(
        source=Path("examples/sample-course/raw/sample_course.pptx"),
        output_dir=tmp_path / "out",
        converted_dir="conversion/cache",
        overview_name="navigation/00_课程总览.md",
    )

    processed = run(config)

    assert len(processed) == 1
    assert (config.output_dir / "notes_skeleton" / "navigation" / "00_课程总览.md").is_file()


@pytest.mark.parametrize("dangling", [False, True])
def test_pipeline_rejects_symlinked_source_file_in_directory(tmp_path: Path, dangling: bool) -> None:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    target = tmp_path / "missing.pdf"
    if not dangling:
        target.write_bytes(b"%PDF-1.4\n")
    (source_root / "external.pdf").symlink_to(target)
    config = PipelineConfig(source=source_root, output_dir=tmp_path / "out")

    with pytest.raises(ValueError, match="source tree contains symlink"):
        run(config)

    assert not (config.output_dir / "raw_extracted").exists()


def test_pipeline_rejects_explicit_source_symlink(tmp_path: Path) -> None:
    target = tmp_path / "source.pdf"
    target.write_bytes(b"%PDF-1.4\n")
    source = tmp_path / "selected.pdf"
    source.symlink_to(target)
    config = PipelineConfig(source=source, output_dir=tmp_path / "out")

    with pytest.raises(ValueError, match="source path is a symlink"):
        run(config)


def test_pipeline_rejects_explicit_unsupported_regular_file(tmp_path: Path) -> None:
    source = tmp_path / "notes.md"
    source.write_text("# Notes\n", encoding="utf-8")
    config = PipelineConfig(source=source, output_dir=tmp_path / "out")

    with pytest.raises(ValueError, match="unsupported explicit source type"):
        run(config)
