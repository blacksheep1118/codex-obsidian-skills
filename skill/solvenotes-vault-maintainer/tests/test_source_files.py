import json
import subprocess
import sys
import zipfile
from pathlib import Path

import check_source_files as csf
import pytest
from check_source_files import ExtractabilityEvidence, issue_code, source_extractability_issues


def manifest_row(
    source: str,
    units: int,
    coverage: str = "已映射：可抽取文本已覆盖",
    limitation: str = "无明显限制",
) -> tuple[Path, list[str]]:
    cells = [
        f"`{source}`",
        f"`{Path(source).suffix}`",
        str(units),
        "text-extraction",
        "[[course/note]]",
        coverage,
        "已复核：源资料未提供独立例题",
        limitation,
        "2026-08-07",
    ]
    return Path("course/source_manifest.md"), cells


def test_pdf_probe_reports_exact_blank_pages_and_count(tmp_path: Path) -> None:
    source = tmp_path / "course" / "lecture.pdf"
    source.parent.mkdir()
    source.write_bytes(b"fake pdf")

    def one_text_one_blank(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="Lecture title\f\f", stderr="")

    issues, evidence, unsupported = source_extractability_issues(
        tmp_path,
        [manifest_row("course/lecture.pdf", 2)],
        strict=True,
        run_command=one_text_one_blank,
    )

    assert unsupported == 0
    assert evidence == [ExtractabilityEvidence("course/lecture.pdf", ".pdf", 2, 2, (2,), True)]
    assert any("blank extractable units" in issue and "units=2" in issue for issue in issues)


def test_pdf_blank_evidence_does_not_fail_honest_partial_status(tmp_path: Path) -> None:
    source = tmp_path / "course" / "lecture.pdf"
    source.parent.mkdir()
    source.write_bytes(b"fake pdf")

    def one_text_one_blank(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="Lecture title\f\f", stderr="")

    issues, evidence, _ = source_extractability_issues(
        tmp_path,
        [
            manifest_row(
                "course/lecture.pdf",
                2,
                coverage="已映射：抽取性已核验；第 2 页文本层空白",
                limitation="第 2 页文本层空白，未做 OCR",
            )
        ],
        strict=True,
        run_command=one_text_one_blank,
    )

    assert issues == []
    assert evidence[0].blank_units == (2,)


def test_pdf_blank_units_must_be_named_in_manifest_limitations(tmp_path: Path) -> None:
    source = tmp_path / "course" / "lecture.pdf"
    source.parent.mkdir()
    source.write_bytes(b"fake pdf")

    def one_text_one_blank(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="Lecture title\f\f", stderr="")

    issues, _, _ = source_extractability_issues(
        tmp_path,
        [
            manifest_row(
                "course/lecture.pdf",
                2,
                coverage="已映射：抽取性已核验",
                limitation="图片未做 OCR",
            )
        ],
        strict=True,
        run_command=one_text_one_blank,
    )

    assert any("blank extractable units are not explicitly recorded" in issue for issue in issues)


def test_pdf_blank_unit_range_is_accepted_in_limitations(tmp_path: Path) -> None:
    source = tmp_path / "course" / "lecture.pdf"
    source.parent.mkdir()
    source.write_bytes(b"fake pdf")

    def one_text_three_blank(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="Title\f\f\f\f", stderr="")

    issues, evidence, _ = source_extractability_issues(
        tmp_path,
        [
            manifest_row(
                "course/lecture.pdf",
                4,
                coverage="已映射：抽取性已核验",
                limitation="p.2–4 文本层空白，未做 OCR",
            )
        ],
        strict=True,
        run_command=one_text_three_blank,
    )

    assert issues == []
    assert evidence[0].blank_units == (2, 3, 4)


def test_pdf_all_blank_units_accept_explicit_whole_document_limitation(tmp_path: Path) -> None:
    source = tmp_path / "course" / "lecture.pdf"
    source.parent.mkdir()
    source.write_bytes(b"fake pdf")

    def three_blank_pages(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="\f\f\f", stderr="")

    issues, evidence, _ = source_extractability_issues(
        tmp_path,
        [
            manifest_row(
                "course/lecture.pdf",
                3,
                coverage="未映射：无可抽取文本",
                limitation="3 页均未抽到可抽取正文，未做 OCR",
            )
        ],
        strict=True,
        run_command=three_blank_pages,
    )

    assert not any("blank extractable units are not explicitly recorded" in issue for issue in issues)
    assert evidence[0].blank_units == (1, 2, 3)


def test_visual_only_source_with_complete_known_limitation_contract_passes_strict_mode(tmp_path: Path) -> None:
    source = tmp_path / "course" / "visual-only.pdf"
    source.parent.mkdir()
    source.write_bytes(b"fake pdf")

    def three_blank_pages(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="\f\f\f", stderr="")

    row = manifest_row(
        "course/visual-only.pdf",
        3,
        coverage="仅映射：文本层无可抽取正文；视觉记录仅支持主题与目标笔记定位",
        limitation="3 页均未抽到可抽取正文，未做 OCR；视觉记录不证明图片细节、公式对象或完整语义覆盖",
    )
    row[1][3] = "visual-page-check"

    issues, evidence, _ = source_extractability_issues(
        tmp_path, [row], strict=True, run_command=three_blank_pages
    )

    assert issues == []
    assert evidence[0].has_extractable_text is False


@pytest.mark.parametrize(
    ("method", "coverage", "limitation"),
    [
        (
            "visual-page-check",
            "仅映射：文本层无可抽取正文；视觉记录仅支持主题定位",
            "3 页均未抽到可抽取正文；视觉记录不证明完整语义覆盖",
        ),
        (
            "visual-page-check",
            "仅映射：文本层无可抽取正文；可抽取文本已覆盖",
            "3 页均未抽到可抽取正文，未做 OCR；视觉记录不证明完整语义覆盖",
        ),
        (
            "text-extraction",
            "仅映射：文本层无可抽取正文；视觉记录仅支持主题定位",
            "3 页均未抽到可抽取正文，未做 OCR；视觉记录不证明完整语义覆盖",
        ),
    ],
)
def test_visual_only_source_without_each_known_limitation_field_fails_strict_mode(
    tmp_path: Path, method: str, coverage: str, limitation: str
) -> None:
    source = tmp_path / "course" / "visual-only.pdf"
    source.parent.mkdir()
    source.write_bytes(b"fake pdf")

    def three_blank_pages(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="\f\f\f", stderr="")

    row = manifest_row("course/visual-only.pdf", 3, coverage=coverage, limitation=limitation)
    row[1][3] = method
    issues, _, _ = source_extractability_issues(tmp_path, [row], strict=True, run_command=three_blank_pages)

    assert any("source has no extractable text without a complete known-limitation contract" in issue for issue in issues)


def test_pdf_probe_fails_on_declared_unit_count_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "course" / "lecture.pdf"
    source.parent.mkdir()
    source.write_bytes(b"fake pdf")

    def one_page(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="Only one page\f", stderr="")

    issues, _, _ = source_extractability_issues(
        tmp_path,
        [manifest_row("course/lecture.pdf", 2, coverage="已映射：抽取性已核验")],
        strict=True,
        run_command=one_page,
    )

    assert any("manifest=2 observed=1" in issue for issue in issues)


def write_pptx(path: Path, slide_texts: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for index, slide_text in enumerate(slide_texts, 1):
            xml = (
                '<p:sld xmlns:p="urn:p" xmlns:a="urn:a"><p:cSld><a:t>'
                + slide_text
                + "</a:t></p:cSld></p:sld>"
            )
            archive.writestr(f"ppt/slides/slide{index}.xml", xml)


def test_pptx_probe_checks_each_slide_including_blank_slide(tmp_path: Path) -> None:
    source = tmp_path / "course" / "lecture.pptx"
    write_pptx(source, ("title", ""))

    issues, evidence, unsupported = source_extractability_issues(
        tmp_path,
        [manifest_row("course/lecture.pptx", 2)],
        strict=True,
    )

    assert unsupported == 0
    assert evidence == [ExtractabilityEvidence("course/lecture.pptx", ".pptx", 2, 2, (2,), True)]
    assert any("blank extractable units" in issue for issue in issues)


def test_docx_probe_checks_text_layer_without_inventing_chunk_count(tmp_path: Path) -> None:
    source = tmp_path / "course" / "handout.docx"
    source.parent.mkdir()
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="urn:w"><w:body><w:p><w:r><w:t>Readable</w:t></w:r></w:p></w:body></w:document>',
        )

    issues, evidence, unsupported = source_extractability_issues(
        tmp_path,
        [manifest_row("course/handout.docx", 15, coverage="已映射：抽取性已核验")],
        strict=True,
    )

    assert issues == []
    assert unsupported == 0
    assert evidence == [ExtractabilityEvidence("course/handout.docx", ".docx", 15, None, (), True)]


def test_legacy_ppt_is_reported_as_unsupported_not_silently_probed(tmp_path: Path) -> None:
    source = tmp_path / "course" / "legacy.ppt"
    source.parent.mkdir()
    source.write_bytes(b"legacy")

    issues, evidence, unsupported = source_extractability_issues(
        tmp_path,
        [manifest_row("course/legacy.ppt", 20, coverage="仅映射：抽取性未核验")],
        strict=True,
    )

    assert issues == []
    assert evidence == []
    assert unsupported == 1


def test_non_strict_source_check_does_not_probe_content(tmp_path: Path) -> None:
    source = tmp_path / "course" / "lecture.pdf"
    source.parent.mkdir()
    source.write_bytes(b"fake pdf")

    def unexpected_run(*args, **kwargs):
        raise AssertionError("non-strict checks must not invoke pdftotext")

    assert source_extractability_issues(
        tmp_path,
        [manifest_row("course/lecture.pdf", 2)],
        strict=False,
        run_command=unexpected_run,
    ) == ([], [], 0)


def test_strict_source_inventory_includes_nested_formal_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "course" / "topic" / "source_manifest.md"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        "| 源文件 | 类型 | 页/slide/记录数 | 抽取方式 | 对应笔记 | 覆盖状态 | 例题状态 | 限制说明 | 最后检查日期 |\n"
        "|---|---|---:|---|---|---|---|---|---|\n"
        "| `course/topic/paper.pdf` | `.pdf` | 1 | pdftotext-page | [[course/topic/note]] | 已映射：文本层 | "
        "已复核：无独立例题 | 未见空白页；未做视觉/OCR | 2026-08-08 |\n",
        encoding="utf-8",
    )

    rows = csf.manifest_rows(tmp_path)

    assert len(rows) == 1
    assert rows[0][0] == manifest


def test_cli_separates_missing_files_from_extractability_issues(tmp_path: Path, monkeypatch, capsys) -> None:
    (tmp_path / "course").mkdir()
    (tmp_path / "course" / "lecture.pdf").write_bytes(b"fake pdf")
    rows = [manifest_row("course/lecture.pdf", 2)]
    evidence = ExtractabilityEvidence("course/lecture.pdf", ".pdf", 2, 2, (2,), True)
    monkeypatch.setattr(csf, "manifest_rows", lambda: rows)
    monkeypatch.setattr(csf, "configured_source_root", lambda _: tmp_path)
    monkeypatch.setattr(
        csf,
        "source_extractability_issues",
        lambda *args, **kwargs: (["blank source unit"], [evidence], 0),
    )
    monkeypatch.setattr(sys, "argv", ["check_source_files.py", "--strict", "--json"])

    assert csf.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["missing_source_files"] == 0
    assert payload["extractability_issues"] == 1
    assert payload["extractability_checks"] == 1
    assert payload["blank_extractable_units"] == 1
    assert payload["source_file_issues"] == 1
    assert payload["blank_unit_evidence"] == [{"source": "course/lecture.pdf", "units": [2]}]


def test_cli_requires_source_root_without_counting_it_as_a_missing_file(monkeypatch, capsys) -> None:
    monkeypatch.setattr(csf, "manifest_rows", lambda: [])
    monkeypatch.setattr(csf, "configured_source_root", lambda _: None)
    monkeypatch.setattr(sys, "argv", ["check_source_files.py", "--strict", "--json"])

    assert csf.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["source_file_check_skipped"] is True
    assert payload["missing_source_files"] == 0
    assert payload["extractability_issues"] == 0
    assert payload["source_file_issues"] == 1


def test_source_file_issue_codes_are_stable() -> None:
    assert issue_code("blank extractable units conflict with complete-text wording") == "BLANK_UNDER_COMPLETE_TEXT"
    assert issue_code("source has no extractable text: course/scan.pdf") == "NO_EXTRACTABLE_TEXT"
    assert issue_code("blank extractable units are not explicitly recorded") == "BLANK_LIMITATION_MISSING"
