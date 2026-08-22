from typing import Any

import mongomock
import pytest

from app.db.mongo_repository import MongoResumeRepository

pytestmark = pytest.mark.filterwarnings("ignore:datetime.datetime.utcnow is deprecated")


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
    assert any("expires" in str(index) for index in indexes.values())
