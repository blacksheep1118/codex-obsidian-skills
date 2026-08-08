from __future__ import annotations

from pathlib import Path
import sys

import pytest

from scripts import clean_latex_from_ppt, extract_legacy_ppt_text, extract_pdf_text, extract_pptx_text
from scripts.extract_legacy_ppt_text import LegacyPptTextResult


@pytest.fixture
def cli_case(request, monkeypatch, tmp_path: Path) -> tuple[object, list[str]]:
    input_path = tmp_path / "input.md"
    input_path.write_text("# Input\n", encoding="utf-8")
    if request.param == "clean":
        return clean_latex_from_ppt, [str(input_path)]
    if request.param == "pptx":
        source = tmp_path / "input.pptx"
        source.write_bytes(b"placeholder")
        monkeypatch.setattr(extract_pptx_text, "extract_pptx", lambda *args, **kwargs: "# PPTX\n")
        return extract_pptx_text, [str(source)]
    if request.param == "pdf":
        source = tmp_path / "input.pdf"
        source.write_bytes(b"%PDF-1.4\n")
        monkeypatch.setattr(extract_pdf_text, "extract_pdf", lambda path: "# PDF\n")
        return extract_pdf_text, [str(source)]
    source = tmp_path / "input.ppt"
    source.write_bytes(b"placeholder")
    monkeypatch.setattr(
        extract_legacy_ppt_text,
        "extract_legacy_ppt_text",
        lambda path: LegacyPptTextResult(source=path, text="Legacy text", text_record_count=1),
    )
    return extract_legacy_ppt_text, [str(source)]


@pytest.mark.parametrize("cli_case", ["clean", "pptx", "pdf", "legacy"], indirect=True)
@pytest.mark.parametrize("kind", ["final", "parent", "ancestor"])
def test_output_clis_reject_symlink_components(
    cli_case: tuple[object, list[str]],
    kind: str,
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    module, arguments = cli_case
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.md"
    sentinel.write_text("keep\n", encoding="utf-8")
    if kind == "final":
        output = tmp_path / "result.md"
        output.symlink_to(sentinel)
    elif kind == "parent":
        parent = tmp_path / "linked-parent"
        parent.symlink_to(outside, target_is_directory=True)
        output = parent / "result.md"
    else:
        ancestor = tmp_path / "linked-ancestor"
        ancestor.symlink_to(outside, target_is_directory=True)
        output = ancestor / "nested" / "result.md"
    monkeypatch.setattr(sys, "argv", [module.__file__, *arguments, "--out", str(output)])

    result = module.main()

    captured = capsys.readouterr()
    assert result == 1
    assert "symlink" in captured.err.lower()
    assert sentinel.read_text(encoding="utf-8") == "keep\n"
    assert not (outside / "result.md").exists()
    assert not (outside / "nested" / "result.md").exists()
