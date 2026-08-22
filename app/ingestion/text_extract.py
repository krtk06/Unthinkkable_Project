from dataclasses import dataclass, field
from io import BytesIO
from typing import Protocol

from docx import Document
from pypdf import PdfReader


@dataclass(frozen=True)
class OCRResult:
    text: str
    confidence: float


class OCRClient(Protocol):
    def ocr(self, file_bytes: bytes, content_type: str) -> OCRResult:
        """Extract text from an image-based document."""


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    page_count: int
    ocr_used: bool
    warnings: list[str] = field(default_factory=list)


def extract_text(
    file_bytes: bytes,
    content_type: str,
    ocr_client: OCRClient | None = None,
    min_text_chars_per_page: int = 20,
    max_pdf_pages: int = 500,
    max_text_chars: int = 20_000,
) -> ExtractionResult:
    normalized_type = content_type.lower()
    if normalized_type == "text/plain":
        try:
            text = file_bytes.decode("utf-8").strip()
        except UnicodeDecodeError as error:
            raise ValueError("UNREADABLE_FILE: plain text is not valid UTF-8") from error
        if len(text) > max_text_chars:
            raise ValueError("TEXT_TOO_LONG: extracted text exceeds the configured limit")
        return ExtractionResult(text=text, page_count=1, ocr_used=False)

    if normalized_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        try:
            document = Document(BytesIO(file_bytes))
            text = "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
        except Exception as error:
            raise ValueError("UNREADABLE_FILE: DOCX could not be parsed") from error
        if len(text) > max_text_chars:
            raise ValueError("TEXT_TOO_LONG: extracted text exceeds the configured limit")
        return ExtractionResult(text=text, page_count=1, ocr_used=False)

    if normalized_type == "application/pdf":
        try:
            reader = PdfReader(BytesIO(file_bytes))
            if reader.is_encrypted:
                raise ValueError("encrypted PDF")
            page_text = [(page.extract_text() or "").strip() for page in reader.pages]
        except ValueError as error:
            raise ValueError("UNREADABLE_FILE: PDF is encrypted or malformed") from error
        except Exception as error:
            raise ValueError("UNREADABLE_FILE: PDF could not be parsed") from error

        text = "\n".join(part for part in page_text if part).strip()
        page_count = len(reader.pages)
        if page_count > max_pdf_pages:
            raise ValueError("PAGE_LIMIT_EXCEEDED: PDF exceeds the configured page limit")
        if page_count == 0 or len(text) >= min_text_chars_per_page * page_count:
            return ExtractionResult(text=text, page_count=page_count, ocr_used=False)
        if ocr_client is None:
            return ExtractionResult(
                text=text,
                page_count=page_count,
                ocr_used=False,
                warnings=["NO_EXTRACTABLE_TEXT"],
            )
        ocr_result = ocr_client.ocr(file_bytes, normalized_type)
        warnings = []
        if not 0 <= ocr_result.confidence <= 1:
            warnings.append("OCR_INVALID_CONFIDENCE")
        elif ocr_result.confidence < 0.7:
            warnings.append("OCR_LOW_CONFIDENCE")
        result = ExtractionResult(
            text=ocr_result.text.strip(),
            page_count=page_count,
            ocr_used=True,
            warnings=warnings,
        )
        if len(result.text) > max_text_chars:
            raise ValueError("TEXT_TOO_LONG: extracted text exceeds the configured limit")
        return result

    raise ValueError("UNREADABLE_FILE: unsupported content type")
