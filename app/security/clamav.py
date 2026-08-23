from io import BytesIO
from typing import Any, cast

import clamd  # type: ignore[import-untyped]


class ClamAVScanner:
    def __init__(self, host: str = "127.0.0.1", port: int = 3310) -> None:
        self.host = host
        self.port = port

    def __call__(self, file_bytes: bytes) -> bool:
        try:
            result = clamd.ClamdNetworkSocket(self.host, self.port).instream(BytesIO(file_bytes))
        except (OSError, ConnectionError, clamd.ConnectionError):
            return False
        result = cast(dict[str, Any], result)
        return bool(result.get("stream", ("ERROR", "missing result"))[0] == "OK")
