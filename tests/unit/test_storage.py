import hashlib
from pathlib import Path

from app.ingestion.storage import LocalFileStorage


def test_local_storage_round_trips_checksum_keyed_file(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    contents = b"resume contents"
    checksum = hashlib.sha256(contents).hexdigest()

    uri = storage.put_original(contents, checksum, "text/plain")

    assert uri == "local://" + checksum
    assert storage.get_original(uri) == contents
    assert (tmp_path / checksum).read_bytes() == contents


def test_local_storage_delete_is_idempotent(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    contents = b"resume contents"
    checksum = hashlib.sha256(contents).hexdigest()
    uri = storage.put_original(contents, checksum, "text/plain")

    storage.delete_original(uri)
    storage.delete_original(uri)

    assert not (tmp_path / checksum).exists()
