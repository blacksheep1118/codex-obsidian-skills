from pathlib import Path

from scripts import extract_pdf_text
from scripts.extract_pdf_text import LOW_COVERAGE_WARNING, extract_pdf, extract_pdf_result


def write_blank_pdf(path: Path) -> None:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 72 72] /Resources << >> /Contents 4 0 R >>",
        b"<< /Length 0 >>\nstream\n\nendstream",
    ]
    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(f"{index} 0 obj\n".encode("ascii"))
        chunks.append(obj)
        chunks.append(b"\nendobj\n")
    xref_offset = sum(len(chunk) for chunk in chunks)
    chunks.append(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    chunks.append(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    chunks.append(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_offset}\n"
            "%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(b"".join(chunks))


def test_extract_pdf_handles_blank_pdf(tmp_path: Path):
    pdf = tmp_path / "blank.pdf"
    write_blank_pdf(pdf)

    output = extract_pdf(pdf)

    assert "# Extracted PDF Text: blank.pdf" in output
    assert "- Backend:" in output
    assert "- Pages: 1" in output
    assert "- Empty text pages: 1" in output
    assert "- Low coverage: true" in output
    assert LOW_COVERAGE_WARNING in output
    assert "## Page 1" in output
    assert "[No extractable text]" in output


def test_extract_pdf_falls_back_when_first_backend_is_all_empty(monkeypatch, tmp_path: Path):
    pdf = tmp_path / "slides.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    calls: list[str] = []

    def empty_pypdf(path: Path) -> list[str]:
        calls.append("pypdf")
        return ["", ""]

    def useful_pdfplumber(path: Path) -> list[str]:
        calls.append("pdfplumber")
        return [
            "This page has enough extracted course text to pass the coverage heuristic.",
            "This second page also has enough extracted text for the fallback backend.",
        ]

    def unused_pdftotext(path: Path) -> list[str]:
        calls.append("pdftotext")
        return ["should not be used"]

    monkeypatch.setattr(extract_pdf_text, "extract_with_pypdf", empty_pypdf)
    monkeypatch.setattr(extract_pdf_text, "extract_with_pdfplumber", useful_pdfplumber)
    monkeypatch.setattr(extract_pdf_text, "extract_with_pdftotext", unused_pdftotext)

    result = extract_pdf_result(pdf)
    output = result.markdown

    assert calls == ["pypdf", "pdfplumber"]
    assert "- Backend: `pdfplumber`" in output
    assert "- Pages: 2" in output
    assert "- Empty text pages: 0" in output
    assert "- Low coverage: false" in output
    assert LOW_COVERAGE_WARNING not in output
    assert result.low_coverage is False
    assert result.backend == "pdfplumber"
    assert result.empty_pages == 0
    assert result.char_count > 0
    assert "enough extracted course text" in output


def test_extract_pdf_warns_when_all_backends_are_low_coverage(monkeypatch, tmp_path: Path):
    pdf = tmp_path / "image_only.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    calls: list[str] = []

    def empty_pypdf(path: Path) -> list[str]:
        calls.append("pypdf")
        return ["", ""]

    def low_pdfplumber(path: Path) -> list[str]:
        calls.append("pdfplumber")
        return ["scan", ""]

    def low_pdftotext(path: Path) -> list[str]:
        calls.append("pdftotext")
        return ["ocr?", ""]

    monkeypatch.setattr(extract_pdf_text, "extract_with_pypdf", empty_pypdf)
    monkeypatch.setattr(extract_pdf_text, "extract_with_pdfplumber", low_pdfplumber)
    monkeypatch.setattr(extract_pdf_text, "extract_with_pdftotext", low_pdftotext)

    result = extract_pdf_result(pdf)

    assert calls == ["pypdf", "pdfplumber", "pdftotext"]
    assert result.low_coverage is True
    assert result.backend == "pdfplumber"
    assert result.empty_pages == 1
    assert result.char_count == 4
    assert LOW_COVERAGE_WARNING in result.markdown
    assert "- Low coverage: true" in result.markdown
