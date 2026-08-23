from app.security.clamav import ClamAVScanner


def test_clamav_scanner_fails_closed_when_service_unavailable() -> None:
    scanner = ClamAVScanner(host="127.0.0.1", port=1)

    assert scanner(b"resume") is False
