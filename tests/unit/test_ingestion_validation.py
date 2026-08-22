import pytest

from app.ingestion.validation import UploadValidationError, validate_upload


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("resume.pdf", "application/pdf"),
        ("resume.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("resume.txt", "text/plain"),
    ],
)
def test_accepts_supported_resume_formats(filename: str, content_type: str) -> None:
    validate_upload(filename, content_type, size_bytes=1_000)


def test_rejects_unsupported_file_type() -> None:
    with pytest.raises(UploadValidationError, match="UNSUPPORTED_FILE"):
        validate_upload("resume.exe", "application/octet-stream", size_bytes=1_000)


def test_rejects_mismatched_mime_type() -> None:
    with pytest.raises(UploadValidationError, match="MIME_TYPE_MISMATCH"):
        validate_upload("resume.pdf", "text/plain", size_bytes=1_000)


def test_accepts_exact_file_size_limit() -> None:
    validate_upload("resume.txt", "text/plain", size_bytes=10, max_file_bytes=10)


def test_rejects_file_over_size_limit() -> None:
    with pytest.raises(UploadValidationError, match="FILE_TOO_LARGE"):
        validate_upload("resume.txt", "text/plain", size_bytes=11, max_file_bytes=10)


def test_rejects_empty_file() -> None:
    with pytest.raises(UploadValidationError, match="EMPTY_FILE"):
        validate_upload("resume.txt", "text/plain", size_bytes=0)
