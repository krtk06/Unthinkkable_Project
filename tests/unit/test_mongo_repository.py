from typing import Any

import mongomock
import pytest

from app.db.mongo_repository import MongoResumeRepository

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def make_repository() -> MongoResumeRepository:
    client: Any = mongomock.MongoClient()
    return MongoResumeRepository(client["resume_screener"])


def test_mongo_repository_embeds_session_candidate_and_match() -> None:
    repository = make_repository()
    session_id = repository.create_session()
    candidate = repository.add_resume(
        session_id,
        filename="resume.txt",
        content_type="text/plain",
        size_bytes=10,
        checksum="a" * 64,
        storage_uri="local://" + "a" * 64,
    )

    repository.save_extraction(
        candidate["id"],
        text="Python",
        page_count=1,
        ocr_used=False,
        warnings=[],
        parsed={"schema_version": "1.0"},
        provenance={"provider": "test", "model": "test", "prompt_version": "v1"},
    )
    repository.save_job_description(session_id, "Must have Python", {"required": []})

    stored = repository.get_candidate(candidate["id"])
    assert stored is not None
    assert stored["resume"]["parsed_json"] == {"schema_version": "1.0"}
    assert stored["resume"]["extraction"]["provider"] == "test"
    session = repository.get_session(session_id)
    assert session is not None
    assert session["job_description"]["raw_text"] == "Must have Python"


def test_mongo_repository_upserts_match_and_creates_ttl_indexes() -> None:
    repository = make_repository()
    session_id = repository.create_session()
    candidate = repository.add_resume(
        session_id,
        filename="resume.txt",
        content_type="text/plain",
        size_bytes=10,
        checksum="b" * 64,
        storage_uri="local://" + "b" * 64,
    )
    match = {"candidate_id": candidate["id"], "score": 8, "model": {"name": "test"}}

    repository.save_match(candidate["id"], match)
    repository.save_match(candidate["id"], {**match, "score": 9})

    stored_match = repository.get_match(candidate["id"])
    assert stored_match is not None
    assert stored_match["score"] == 9
    indexes = repository.sessions.index_information()
    assert indexes["expires_at_1"]["expireAfterSeconds"] == 0


def test_mongo_repository_rejects_duplicate_checksum_in_session() -> None:
    repository = make_repository()
    session_id = repository.create_session()
    values = {
        "filename": "resume.txt",
        "content_type": "text/plain",
        "size_bytes": 10,
        "checksum": "c" * 64,
        "storage_uri": "local://c",
    }
    repository.add_resume(session_id, **values)

    with pytest.raises(ValueError, match="DUPLICATE_RESUME"):
        repository.add_resume(session_id, **values)


def test_mongo_match_update_targets_only_requested_candidate() -> None:
    repository = make_repository()
    session_id = repository.create_session()
    first = repository.add_resume(
        session_id,
        filename="one.txt",
        content_type="text/plain",
        size_bytes=1,
        checksum="e" * 64,
        storage_uri="local://e",
    )
    second = repository.add_resume(
        session_id,
        filename="two.txt",
        content_type="text/plain",
        size_bytes=1,
        checksum="f" * 64,
        storage_uri="local://f",
    )

    repository.save_match(first["id"], {"candidate_id": first["id"], "score": 8})
    repository.save_match(second["id"], {"candidate_id": second["id"], "score": 9})
    repository.save_match(first["id"], {"candidate_id": first["id"], "score": 7})

    first_match = repository.get_match(first["id"])
    second_match = repository.get_match(second["id"])
    assert first_match is not None
    assert second_match is not None
    assert first_match["score"] == 7
    assert second_match["score"] == 9


def test_mongo_repository_distinguishes_missing_session() -> None:
    repository = make_repository()

    with pytest.raises(ValueError, match="SESSION_NOT_FOUND"):
        repository.add_resume("missing", checksum="d" * 64)
