from pathlib import Path
from zipfile import ZipFile

from scripts.extract_pptx_text import extract_pptx, extract_pptx_with_zip_result


def test_extract_pptx_sample_contains_ordered_slide_text():
    sample = Path("examples/sample-course/raw/sample_course.pptx")
    output = extract_pptx(sample)

    assert "# Extracted PPTX Text: sample_course.pptx" in output
    assert "## Slide 1: 机器学习导论" in output
    assert "- 经验风险与泛化" in output
    assert "- 知识点精简复习版_含公式.md" in output
    assert "- Backend: `python-pptx`" in output
    assert "- Slides:" in output


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
