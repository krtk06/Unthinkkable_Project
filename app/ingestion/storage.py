import hashlib
import os
import tempfile
from pathlib import Path


class LocalFileStorage:
    """Private local development storage with checksum-addressed immutable files."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)

    def put_original(self, file_bytes: bytes, checksum: str, content_type: str) -> str:
        actual_checksum = hashlib.sha256(file_bytes).hexdigest()
        if actual_checksum != checksum:
            raise ValueError("checksum does not match file contents")
        destination = self._path_for_uri(f"local://{checksum}")
        if destination.exists():
            return f"local://{checksum}"
        with tempfile.NamedTemporaryFile(dir=self.root, delete=False) as temporary:
            temporary.write(file_bytes)
            temporary_path = Path(temporary.name)
        os.chmod(temporary_path, 0o600)
        temporary_path.replace(destination)
        return f"local://{checksum}"

    def get_original(self, uri: str) -> bytes:
        return self._path_for_uri(uri).read_bytes()

    def delete_original(self, uri: str) -> None:
        self._path_for_uri(uri).unlink(missing_ok=True)

    def _path_for_uri(self, uri: str) -> Path:
        prefix, _, checksum = uri.partition("://")
        invalid_checksum = any(char not in "0123456789abcdef" for char in checksum)
        if prefix != "local" or len(checksum) != 64 or invalid_checksum:
            raise ValueError("invalid local storage URI")
        return self.root / checksum
