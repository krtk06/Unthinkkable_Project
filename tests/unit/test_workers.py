from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.db.repository import ResumeRepository
from app.domain.job import JobRequirements
from app.domain.match import MatchResult, ModelMetadata
from app.domain.resume import ExtractedResume
from app.ingestion.text_extract import ExtractionResult
from app.workers.tasks import ResumeWorker, process_batch


class FakeStorage:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files

    def get_original(self, uri: str) -> bytes:
        return self.files[uri]


class FakeExtractor:
    def __init__(self, failing_uri: str) -> None:
        self.failing_uri = failing_uri
        self.current_uri = ""

    def extract(self, file_bytes: bytes, content_type: str) -> ExtractionResult:
        if file_bytes.decode() == self.failing_uri:
            raise ValueError("UNREADABLE_FILE: fixture failure")
        return ExtractionResult(text="resume text", page_count=1, ocr_used=False)


class FakeLLM:
    def extract_resume(self, text: str) -> ExtractedResume:
        return ExtractedResume.model_validate(
            {
                "schema_version": "1.0",
                "candidate": {
                    "name": "Ada",
                    "contact": {"email": None, "phone": None, "url": None},
                    "location": None,
                },
                "skills": ["Python"],
                "experience": [],
                "education": [],
                "certifications": [],
                "languages": [],
                "warnings": [],
            }
        )


class FakeScoringClient:
    def __init__(self, candidate_id: str) -> None:
        self.candidate_id = candidate_id

    def score_match(
        self,
        requirements: JobRequirements,
        resume: ExtractedResume,
        embedding_context: str,
    ) -> MatchResult:
        return MatchResult(
            candidate_id=self.candidate_id,
            score=8,
            required_coverage=1,
            preferred_coverage=0,
            strengths=["Python"],
            gaps=[],
            evidence=[],
            uncertainty=[],
            model=ModelMetadata(provider="test", model="test", prompt_version="v1"),
        )


def make_worker(tmp_path: Path) -> tuple[Session, ResumeWorker, list[str]]:
    engine = create_engine(f"sqlite:///{tmp_path / 'workers.db'}")
    Base.metadata.create_all(engine)
    db = Session(engine)
    repository = ResumeRepository()
    session = repository.create_session(db)
    files = {"local://one": b"one", "local://two": b"two"}
    repository.add_resume(
        db,
        session.id,
        filename="one.txt",
        content_type="text/plain",
        size_bytes=3,
        checksum="1" * 64,
        storage_uri="local://one",
    )
    repository.add_resume(
        db,
        session.id,
        filename="two.txt",
        content_type="text/plain",
        size_bytes=3,
        checksum="2" * 64,
        storage_uri="local://two",
    )
    resume_ids = [
        candidate.resume_file.id for candidate in session.candidates if candidate.resume_file
    ]
    worker = ResumeWorker(
        db,
        repository,
        FakeStorage(files),
        FakeExtractor("two"),
        FakeLLM(),
        provider="test",
        model="test-model",
        prompt_version="resume-extraction-v1",
    )
    return db, worker, resume_ids


def test_batch_worker_isolates_resume_failure(tmp_path: Path) -> None:
    db, worker, resume_ids = make_worker(tmp_path)

    statuses = process_batch(worker, resume_ids)

    assert list(statuses.values()) == ["parsed", "failed"]
    stored_statuses = []
    for resume_id in resume_ids:
        stored_resume = worker.repository.get_resume(db, resume_id)
        assert stored_resume is not None
        stored_statuses.append(stored_resume.status)
    assert stored_statuses == ["parsed", "failed"]


def test_score_worker_persists_match_result(tmp_path: Path) -> None:
    db, worker, resume_ids = make_worker(tmp_path)
    resume = worker.repository.get_resume(db, resume_ids[0])
    assert resume is not None
    worker.process_resume(resume.id)

    result = worker.score_candidate(
        resume.candidate.id,
        JobRequirements(title="Engineer"),
        FakeScoringClient(resume.candidate.id),
    )

    assert result.candidate_id == resume.candidate.id
    assert resume.candidate.match is not None
    assert resume.candidate.match.score == 8

    repeated = worker.score_candidate(
        resume.candidate.id,
        JobRequirements(title="Engineer"),
        FakeScoringClient(resume.candidate.id),
    )

    assert repeated.score == 8
