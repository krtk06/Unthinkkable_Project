from io import BytesIO

import pytest
from docx import Document
from pypdf import PdfWriter

from app.ingestion.text_extract import OCRResult, extract_text


def make_pdf(text: str | None = None) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    if text is not None:
        # A minimal text fixture is represented by the OCR double in this unit suite.
        return text.encode()
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def make_docx(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


class FakeOCR:
    def __init__(self, result: OCRResult) -> None:
        self.result = result
        self.calls = 0

    def ocr(self, file_bytes: bytes, content_type: str) -> OCRResult:
        self.calls += 1
        return self.result


def test_extracts_plain_text_as_utf8() -> None:
    result = extract_text("Résumé: ingénieure".encode(), "text/plain")

    assert result.text == "Résumé: ingénieure"
    assert result.page_count == 1
    assert result.ocr_used is False
    assert result.warnings == []


def test_extracts_docx_paragraphs() -> None:
    result = extract_text(
        make_docx("Python engineer"),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert result.text == "Python engineer"
    assert result.page_count == 1
    assert result.ocr_used is False


def test_uses_ocr_for_pdf_with_no_extractable_text() -> None:
    ocr = FakeOCR(OCRResult(text="Scanned resume", confidence=0.95))

    result = extract_text(make_pdf(), "application/pdf", ocr_client=ocr)

    assert result.text == "Scanned resume"
    assert result.ocr_used is True
    assert ocr.calls == 1


def test_warns_when_ocr_confidence_is_low() -> None:
    ocr = FakeOCR(OCRResult(text="Unreadable resume", confidence=0.3))

    result = extract_text(make_pdf(), "application/pdf", ocr_client=ocr)

    assert "OCR_LOW_CONFIDENCE" in result.warnings


def test_rejects_corrupt_pdf() -> None:
    with pytest.raises(ValueError, match="UNREADABLE_FILE"):
        extract_text(b"not a pdf", "application/pdf")
