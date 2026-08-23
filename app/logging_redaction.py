"""Log redaction filter for PII."""

import logging
import re

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}")
# Resume text markers - redact long text blocks that look like resume content
_LONG_TEXT_RE = re.compile(
    r"(?s)(experience|education|skills|summary|objective|work history|employment)[\s:].{100,}?"
)


class PIIRedactionFilter(logging.Filter):
    """Removes emails, phone numbers, and long resume-like text from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redact(str(record.msg))
        if record.args:
            record.args = tuple(
                self._redact(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True

    def _redact(self, text: str) -> str:
        text = _EMAIL_RE.sub("[EMAIL REDACTED]", text)
        text = _PHONE_RE.sub("[PHONE REDACTED]", text)
        text = _LONG_TEXT_RE.sub("[LONG TEXT REDACTED]", text)
        return text


def install_pii_redaction() -> None:
    """Attach the PII redaction filter to the root logger."""
    root = logging.getLogger()
    root.addFilter(PIIRedactionFilter())