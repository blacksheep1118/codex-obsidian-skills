from pathlib import Path

from scripts.extract_pptx_text import extract_pptx


def test_extract_pptx_sample_contains_ordered_slide_text():
    sample = Path("examples/sample-course/raw/sample_course.pptx")
    output = extract_pptx(sample)

    assert "# Extracted PPTX Text: sample_course.pptx" in output
    assert "## Slide 1: 机器学习导论" in output
    assert "- 经验风险与泛化" in output
    assert "- 知识点精简复习版_含公式.md" in output
