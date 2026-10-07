import os
import subprocess
import sys
from pathlib import Path

import pytest
from normalize_source_manifests import (
    UnsafeLegacyRowError,
    normalize_line,
    normalized_text,
    source_manifest_paths,
)


@pytest.fixture(autouse=True)
def isolated_manifest_root(tmp_path: Path, monkeypatch) -> Path:
    """Keep each test independent of host-private source registry settings."""
    root = tmp_path.with_name(tmp_path.name + "-vault-sources")
    root.mkdir()
    (tmp_path / "AGENT.md").write_text("# Test vault rules\n", encoding="utf-8")
    monkeypatch.setenv("SOLVENOTES_MANIFEST_ROOT", str(root))
    return root


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


def test_manifest_enumeration_includes_nested_topics_and_excludes_templates(
    tmp_path: Path, isolated_manifest_root: Path
) -> None:
    nested = isolated_manifest_root / "计算机视觉" / "图像Raw域去噪" / "source_manifest.md"
    template = isolated_manifest_root / "模板" / "source_manifest.md"
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


def run_normalizer(root: Path, registry: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        SOLVENOTES_VAULT_ROOT=str(root),
        SOLVENOTES_MANIFEST_ROOT=str(registry),
        PYTHONDONTWRITEBYTECODE="1",
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "normalize_source_manifests.py"
    return subprocess.run(
        [sys.executable, str(script), *args], env=env, capture_output=True, text=True, timeout=30, check=False
    )


def test_normalize_writes_external_manifest_without_touching_notes(
    tmp_path: Path, isolated_manifest_root: Path
) -> None:
    note = tmp_path / "course" / "note.md"
    note.parent.mkdir()
    note.write_text("# course note\n", encoding="utf-8")
    manifest = isolated_manifest_root / "course" / "source_manifest.md"
    manifest.parent.mkdir()
    original = (
        "| 源文件 | old header |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        "| `course/source.pdf` | `.pdf` | 2 | pdftotext-page | [[course/note]] | "
        "已映射：抽取性已核验 | 已复核：未提供独立例题 | 未做视觉/OCR | 2026-08-07 |\n"
    )
    manifest.write_text(original, encoding="utf-8")
    before = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    check = run_normalizer(tmp_path, isolated_manifest_root, "--check")
    assert check.returncode == 1, check.stdout + check.stderr
    assert manifest.read_text(encoding="utf-8") == original
    write = run_normalizer(tmp_path, isolated_manifest_root)
    assert write.returncode == 0, write.stdout + write.stderr
    assert "CHANGED vault_sources/course/source_manifest.md" in write.stdout
    assert manifest.read_text(encoding="utf-8") == normalized_text(original, "2026-08-07")
    assert {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before
    repeated = run_normalizer(tmp_path, isolated_manifest_root, "--check")
    assert repeated.returncode == 0, repeated.stdout + repeated.stderr


@pytest.mark.parametrize("state", ["missing", "empty", "symlink_only"])
def test_normalize_does_not_succeed_without_safe_external_manifests(
    tmp_path: Path, isolated_manifest_root: Path, state: str
) -> None:
    if state == "missing":
        isolated_manifest_root.rmdir()
    if state == "symlink_only":
        outside = tmp_path / "outside.md"
        outside.write_text("# untouched\n", encoding="utf-8")
        (isolated_manifest_root / "source_manifest.md").symlink_to(outside)

    result = run_normalizer(tmp_path, isolated_manifest_root)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    expected = "SOURCE_MANIFESTS_MISSING" if state == "empty" else "SOURCE_MANIFEST_ROOT_UNAVAILABLE"
    assert expected in result.stdout
    if state == "symlink_only":
        assert outside.read_text(encoding="utf-8") == "# untouched\n"
