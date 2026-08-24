from io import BytesIO
from pathlib import Path
from typing import Any, cast

import clamd  # type: ignore[import-untyped]


class ClamAVScanner:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 3310,
        socket_path: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.socket_path = socket_path

    def __call__(self, file_bytes: bytes) -> bool:
        if self.socket_path and Path(self.socket_path).exists():
            try:
                result = clamd.ClamdUnixSocket(path=self.socket_path).instream(
                    BytesIO(file_bytes)
                )
            except (OSError, ConnectionError, clamd.ConnectionError):
                pass
            else:
                return self._parse(result)
        try:
            result = clamd.ClamdNetworkSocket(self.host, self.port).instream(
                BytesIO(file_bytes)
            )
        except (OSError, ConnectionError, clamd.ConnectionError):
            return False
        return self._parse(result)

    @staticmethod
    def _parse(result: Any) -> bool:
        result = cast(dict[str, Any], result)
        return bool(result.get("stream", ("ERROR", "missing result"))[0] == "OK")
