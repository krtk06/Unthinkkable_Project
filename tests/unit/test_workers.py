import mongomock
import pytest

from app.db.mongo_repository import MongoResumeRepository
from app.domain.job import JobRequirements
from app.domain.match import MatchResult, ModelMetadata
from app.domain.resume import ExtractedResume
from app.ingestion.text_extract import ExtractionResult
from app.workers.tasks import LocalTaskQueue, ResumeWorker, process_batch

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


class FakeStorage:
    def get_original(self, uri: str) -> bytes:
        return uri.encode()


class FakeExtractor:
    def extract(self, file_bytes: bytes, content_type: str) -> ExtractionResult:
        if file_bytes == b"failed":
            raise ValueError("UNREADABLE_FILE")
        return ExtractionResult(text="resume text", page_count=1, ocr_used=False)


class FakeParser:
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


class FailingScoringClient:
    def score_match(
        self,
        requirements: JobRequirements,
        resume: ExtractedResume,
        embedding_context: str,
    ) -> MatchResult:
        raise TimeoutError("provider unavailable")


def make_worker() -> tuple[MongoResumeRepository, ResumeWorker, list[str]]:
    repository = MongoResumeRepository(mongomock.MongoClient()["resume_screener"])
    session_id = repository.create_session()
    candidates = [
        repository.add_resume(
            session_id,
            filename=f"resume-{value}.txt",
            content_type="text/plain",
            size_bytes=3,
            checksum=value * 64,
            storage_uri="local://" + value,
        )
        for value in ("one", "two")
    ]
    worker = ResumeWorker(
        repository,
        FakeStorage(),
        FakeExtractor(),
        FakeParser(),
        provider="test",
        model="test-model",
        prompt_version="resume-extraction-v1",
    )
    return repository, worker, [candidate["id"] for candidate in candidates]


def test_batch_worker_isolates_resume_failure() -> None:
    repository, worker, candidate_ids = make_worker()
    repository._update_candidate(candidate_ids[1], {"resume.storage_uri": "failed"})

    statuses = process_batch(worker, candidate_ids)

    assert list(statuses.values()) == ["parsed", "failed"]


def test_score_worker_persists_and_reuses_match() -> None:
    repository, worker, candidate_ids = make_worker()
    worker.process_resume(candidate_ids[0])
    client = FakeScoringClient(candidate_ids[0])

    first = worker.score_candidate(candidate_ids[0], JobRequirements(title="Engineer"), client)
    second = worker.score_candidate(candidate_ids[0], JobRequirements(title="Engineer"), client)

    assert first.score == 8
    assert second.score == 8
    stored_match = repository.get_match(candidate_ids[0])
    assert stored_match is not None
    assert stored_match["score"] == 8


def test_local_task_queue_defers_and_runs_work() -> None:
    queue = LocalTaskQueue()
    completed: list[str] = []
    queue.enqueue(lambda: completed.append("done"))

    assert queue.pending_count() == 1
    assert completed == []
    queue.run_next()
    assert completed == ["done"]


def test_failed_scoring_returns_candidate_to_retryable_state() -> None:
    repository, worker, candidate_ids = make_worker()
    worker.process_resume(candidate_ids[0])

    try:
        worker.score_candidate(
            candidate_ids[0], JobRequirements(title="Engineer"), FailingScoringClient()
        )
    except TimeoutError:
        pass
    else:
        raise AssertionError("provider failure should be raised")

    candidate = repository.get_candidate(candidate_ids[0])
    assert candidate is not None
    assert candidate["resume"]["status"] == "parsed"
