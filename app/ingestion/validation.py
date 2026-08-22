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
