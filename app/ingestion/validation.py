from collections.abc import Callable
from pathlib import Path

SUPPORTED_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".txt": {"text/plain"},
}
DEFAULT_MAX_FILE_BYTES = 10 * 1024 * 1024


class UploadValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def validate_upload(
    filename: str,
    content_type: str,
    size_bytes: int,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    file_bytes: bytes | None = None,
    malware_scanner: Callable[[bytes], bool] | None = None,
) -> None:
    suffix = Path(filename).suffix.lower()
    allowed_types = SUPPORTED_TYPES.get(suffix)
    if allowed_types is None:
        raise UploadValidationError(
            "UNSUPPORTED_FILE", "Only PDF, DOCX, and plain text are supported"
        )
    if content_type.lower() not in allowed_types:
        raise UploadValidationError(
            "MIME_TYPE_MISMATCH", "File extension and MIME type do not match"
        )
    if size_bytes <= 0:
        raise UploadValidationError("EMPTY_FILE", "Uploaded file is empty")
    if size_bytes > max_file_bytes:
        raise UploadValidationError(
            "FILE_TOO_LARGE", "Uploaded file exceeds the configured size limit"
        )
    if file_bytes is None:
        raise UploadValidationError("CONTENT_REQUIRED", "File bytes are required for validation")
    if len(file_bytes) != size_bytes:
        raise UploadValidationError("SIZE_MISMATCH", "Declared size does not match file contents")
    signatures = {
        ".pdf": file_bytes.startswith(b"%PDF-"),
        ".docx": file_bytes.startswith(b"PK\x03\x04"),
        ".txt": _is_utf8_text(file_bytes),
    }
    if not signatures[suffix]:
        raise UploadValidationError(
            "INVALID_FILE_SIGNATURE", "File content does not match its type"
        )
    if malware_scanner is None:
        raise UploadValidationError("SCANNER_UNAVAILABLE", "A malware scanner is required")
    if not malware_scanner(file_bytes):
        raise UploadValidationError("MALWARE_DETECTED", "Malware scanner rejected the upload")


def _is_utf8_text(file_bytes: bytes) -> bool:
    try:
        file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True
