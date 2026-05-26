from pathlib import Path

from pypdf import PdfWriter

from scripts.extract_pdf_text import extract_pdf


def test_extract_pdf_handles_blank_pdf(tmp_path: Path):
    pdf = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf.open("wb") as fh:
        writer.write(fh)

    output = extract_pdf(pdf)

    assert "# Extracted PDF Text: blank.pdf" in output
    assert "## Page 1" in output
    assert "[No extractable text]" in output
