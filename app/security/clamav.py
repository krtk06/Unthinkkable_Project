from io import BytesIO

import clamd


class ClamAVScanner:
    def __init__(self, host: str = "127.0.0.1", port: int = 3310) -> None:
        self.host = host
        self.port = port

    def __call__(self, file_bytes: bytes) -> bool:
        result = clamd.ClamdNetworkSocket(self.host, self.port).instream(BytesIO(file_bytes))
        return result.get("stream", ("ERROR", "missing result"))[0] == "OK"
