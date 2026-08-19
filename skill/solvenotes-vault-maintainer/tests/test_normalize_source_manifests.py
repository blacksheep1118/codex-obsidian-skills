import pytest
from normalize_source_manifests import (
    UnsafeLegacyRowError,
    normalize_line,
    normalized_text,
    source_manifest_paths,
)


def test_nine_column_row_is_only_formatted() -> None:
    row = (
        "| `course/source.pdf` | `.pdf` | 2 | pdftotext-page | [[course/note]] | "
        "已映射：抽取性已核验 | 已复核：未提供独立例题 | 无明显限制 | 2026-08-07 |"
    )

    assert normalize_line(row, "2099-01-01") == row


def test_legacy_row_does_not_manufacture_coverage_or_example_claims() -> None:
    row = "| `course/source.pdf` | `.pdf` | 2 | pdftotext-page | [[course/note]] | 低 |"

    with pytest.raises(UnsafeLegacyRowError, match="needs manual coverage, example"):
        normalize_line(row, "2026-08-07")


def test_unsafe_manifest_is_not_partially_normalized() -> None:
    text = (
        "| old header |\n"
        "|---|---|---|---|---|---|\n"
        "| `course/source.pdf` | `.pdf` | 2 | pdftotext-page | [[course/note]] | 低 |\n"
    )

    with pytest.raises(UnsafeLegacyRowError):
        normalized_text(text, "2026-08-07")


def test_manifest_enumeration_includes_nested_topics_and_excludes_templates(tmp_path) -> None:
    nested = tmp_path / "计算机视觉" / "图像Raw域去噪" / "source_manifest.md"
    template = tmp_path / "模板" / "source_manifest.md"
    nested.parent.mkdir(parents=True)
    template.parent.mkdir()
    nested.write_text("# formal\n", encoding="utf-8")
    template.write_text("# scaffold\n", encoding="utf-8")

    assert source_manifest_paths(tmp_path) == [nested]


def test_web_source_table_is_not_rewritten_as_a_local_nine_column_table() -> None:
    text = (
        "| 来源 | URL | 类型 | 访问状态 | 用途 |\n"
        "|---|---|---|---|---|\n"
        "| Official source | https://example.org | webpage | 可访问 | 学习资料 |\n"
    )

    assert normalized_text(text, "2026-08-07") == text
