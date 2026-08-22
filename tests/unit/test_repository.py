from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.repository import ResumeRepository


def make_repository(tmp_path: Path) -> tuple[Session, ResumeRepository]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    return Session(engine), ResumeRepository()


def test_repository_persists_resume_and_parsed_payload(tmp_path: Path) -> None:
    db, repository = make_repository(tmp_path)
    session = repository.create_session(db)

    resume = repository.add_resume(
        db,
        session.id,
        filename="resume.pdf",
        content_type="application/pdf",
        size_bytes=123,
        checksum="a" * 64,
        storage_uri="local://" + "a" * 64,
    )
    repository.update_stage(db, resume.id, "text_extracted")
    repository.save_parsed_resume(db, resume.id, {"schema_version": "1.0", "skills": ["Python"]})

    db.refresh(resume)
    assert resume.status == "parsed"
    assert resume.parsed_json == {"schema_version": "1.0", "skills": ["Python"]}
    assert resume.candidate.session_id == session.id


def test_repository_rejects_duplicate_resume_checksum_per_session(tmp_path: Path) -> None:
    db, repository = make_repository(tmp_path)
    session = repository.create_session(db)
    checksum = "b" * 64
    repository.add_resume(
        db,
        session.id,
        filename="resume.txt",
        content_type="text/plain",
        size_bytes=10,
        checksum=checksum,
        storage_uri="local://" + checksum,
    )

    try:
        repository.add_resume(
            db,
            session.id,
            filename="resume.txt",
            content_type="text/plain",
            size_bytes=10,
            checksum=checksum,
            storage_uri="local://" + checksum,
        )
    except ValueError as error:
        assert str(error) == "DUPLICATE_RESUME"
    else:
        raise AssertionError("duplicate checksum should be rejected")


def test_delete_session_removes_owned_candidate_data(tmp_path: Path) -> None:
    db, repository = make_repository(tmp_path)
    session = repository.create_session(db)
    resume = repository.add_resume(
        db,
        session.id,
        filename="resume.txt",
        content_type="text/plain",
        size_bytes=10,
        checksum="c" * 64,
        storage_uri="local://" + "c" * 64,
    )

    repository.save_parsed_resume(db, resume.id, {"schema_version": "1.0"})
    storage = type("Storage", (), {"delete_original": lambda self, uri: deleted.append(uri)})()
    deleted: list[str] = []
    repository.delete_session(db, session.id, storage=storage)

    assert repository.get_resume(db, resume.id) is None
    assert deleted == ["local://" + "c" * 64]


def test_repository_persists_extraction_metadata_and_attempt(tmp_path: Path) -> None:
    db, repository = make_repository(tmp_path)
    session = repository.create_session(db)
    resume = repository.add_resume(
        db,
        session.id,
        filename="resume.txt",
        content_type="text/plain",
        size_bytes=10,
        checksum="d" * 64,
        storage_uri="local://" + "d" * 64,
    )

    repository.record_attempt(db, resume.id, "parse", "started", attempt_number=1)
    repository.save_extraction(
        db,
        resume.id,
        text="resume text",
        page_count=1,
        ocr_used=False,
        warnings=["warning"],
        parsed={"schema_version": "1.0"},
    )

    db.refresh(resume)
    assert resume.extracted_text == "resume text"
    assert resume.page_count == 1
    assert resume.ocr_used is False
    assert resume.extraction_warnings == ["warning"]
    assert len(resume.attempts) == 1


def test_repository_sequences_attempt_numbers(tmp_path: Path) -> None:
    db, repository = make_repository(tmp_path)
    session = repository.create_session(db)
    resume = repository.add_resume(
        db,
        session.id,
        filename="resume.txt",
        content_type="text/plain",
        size_bytes=10,
        checksum="e" * 64,
        storage_uri="local://" + "e" * 64,
    )

    first = repository.record_attempt(db, resume.id, "parse", "failed")
    second = repository.record_attempt(db, resume.id, "parse", "started")

    assert first.attempt_number == 1
    assert second.attempt_number == 2
