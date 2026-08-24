from pathlib import Path
from typing import Any

from app.security.clamav import ClamAVScanner


def test_clamav_scanner_fails_closed_when_service_unavailable() -> None:
    scanner = ClamAVScanner(host="127.0.0.1", port=1)

    assert scanner(b"resume") is False


def test_clamav_scanner_prefers_unix_socket_when_present(
    tmp_path: Path, monkeypatch: Any
) -> None:
    import clamd  # type: ignore[import-untyped]

    calls: list[str] = []

    class FakeUnixSocket:
        def __init__(
            self, path: str = "/run/clamav/clamd.ctl", timeout: float | None = None
        ) -> None:
            calls.append("unix")

        def instream(self, stream: Any) -> dict[str, Any]:
            return {"stream": ("OK", "everything fine")}

    class FakeNetworkSocket:
        def __init__(
            self, host: str = "127.0.0.1", port: int = 3310, timeout: float | None = None
        ) -> None:
            calls.append("network")

        def instream(self, stream: Any) -> dict[str, Any]:
            return {"stream": ("FOUND", "Eicar-Test-Signature")}

    socket_file = tmp_path / "clamd.ctl"
    socket_file.write_text("")

    monkeypatch.setattr(clamd, "ClamdUnixSocket", FakeUnixSocket)
    monkeypatch.setattr(clamd, "ClamdNetworkSocket", FakeNetworkSocket)

    scanner = ClamAVScanner(socket_path=str(socket_file))

    assert scanner(b"resume") is True
    assert calls == ["unix"]


def test_clamav_scanner_falls_back_to_tcp_when_socket_missing(
    tmp_path: Path, monkeypatch: Any
) -> None:
    import clamd

    calls: list[str] = []

    class FakeUnixSocket:
        def __init__(
            self, path: str = "/run/clamav/clamd.ctl", timeout: float | None = None
        ) -> None:
            calls.append("unix")

        def instream(self, stream: Any) -> dict[str, Any]:
            return {"stream": ("OK", "everything fine")}

    class FakeNetworkSocket:
        def __init__(
            self, host: str = "127.0.0.1", port: int = 3310, timeout: float | None = None
        ) -> None:
            calls.append("network")

        def instream(self, stream: Any) -> dict[str, Any]:
            return {"stream": ("OK", "everything fine")}

    monkeypatch.setattr(clamd, "ClamdUnixSocket", FakeUnixSocket)
    monkeypatch.setattr(clamd, "ClamdNetworkSocket", FakeNetworkSocket)

    scanner = ClamAVScanner(socket_path=str(tmp_path / "missing.ctl"))

    assert scanner(b"resume") is True
    assert calls == ["network"]


def test_clamav_scanner_treats_unix_socket_connection_error_as_fallback(
    tmp_path: Path, monkeypatch: Any
) -> None:
    import clamd

    calls: list[str] = []

    class BrokenUnixSocket:
        def __init__(
            self, path: str = "/run/clamav/clamd.ctl", timeout: float | None = None
        ) -> None:
            calls.append("unix")

        def instream(self, stream: Any) -> dict[str, Any]:
            raise ConnectionError("connection refused")

    class FakeNetworkSocket:
        def __init__(
            self, host: str = "127.0.0.1", port: int = 3310, timeout: float | None = None
        ) -> None:
            calls.append("network")

        def instream(self, stream: Any) -> dict[str, Any]:
            return {"stream": ("OK", "everything fine")}

    socket_file = tmp_path / "clamd.ctl"
    socket_file.write_text("")

    monkeypatch.setattr(clamd, "ClamdUnixSocket", BrokenUnixSocket)
    monkeypatch.setattr(clamd, "ClamdNetworkSocket", FakeNetworkSocket)

    scanner = ClamAVScanner(socket_path=str(socket_file))

    assert scanner(b"resume") is True
    assert calls == ["unix", "network"]
