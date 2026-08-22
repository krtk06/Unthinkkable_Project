from collections import deque
from collections.abc import Callable, Mapping
from threading import Lock
from typing import Protocol

from sqlalchemy.orm import Session

from app.db.repository import ResumeRepository
from app.domain.job import JobRequirements
from app.domain.match import MatchResult
from app.domain.resume import ExtractedResume
from app.ingestion.text_extract import ExtractionResult
from app.matching.embeddings import EmbeddingClient, embed_candidate
from app.matching.scoring import ScoringClient
from app.matching.scoring import score_candidate as score_match

_score_lock = Lock()


class FileStorage(Protocol):
    def get_original(self, uri: str) -> bytes: ...


class TextExtractor(Protocol):
    def extract(self, file_bytes: bytes, content_type: str) -> ExtractionResult: ...


class ResumeParser(Protocol):
    def extract_resume(self, text: str) -> ExtractedResume: ...


class ResumeWorker:
    def __init__(
        self,
        db: Session,
        repository: ResumeRepository,
        storage: FileStorage,
        extractor: TextExtractor,
        parser: ResumeParser,
        *,
        provider: str,
        model: str,
        prompt_version: str,
        embedding_client: EmbeddingClient | None = None,
        embedding_model: str = "",
    ) -> None:
        self.db = db
        self.repository = repository
        self.storage = storage
        self.extractor = extractor
        self.parser = parser
        self.provider = provider
        self.model = model
        self.prompt_version = prompt_version
        self.embedding_client = embedding_client
        self.embedding_model = embedding_model

    def process_resume(self, resume_id: str) -> str:
        resume = self.repository.get_resume(self.db, resume_id)
        if resume is None:
            raise ValueError("RESUME_NOT_FOUND")
        if resume.status in {"parsed", "scored"}:
            return resume.status
        self.repository.record_attempt(self.db, resume_id, "parse", "started")
        try:
            extraction = self.extractor.extract(
                self.storage.get_original(resume.storage_uri), resume.content_type
            )
            self.repository.update_stage(self.db, resume_id, "text_extracted")
            parsed = self.parser.extract_resume(extraction.text)
            self.repository.save_extraction(
                self.db,
                resume_id,
                text=extraction.text,
                page_count=extraction.page_count,
                ocr_used=extraction.ocr_used,
                warnings=extraction.warnings,
                parsed=parsed.model_dump(mode="json"),
                provider=self.provider,
                model=self.model,
                prompt_version=self.prompt_version,
            )
            if self.embedding_client is not None:
                self.repository.save_embedding(
                    self.db,
                    resume_id,
                    embed_candidate(parsed, self.embedding_client),
                    self.embedding_model,
                )
            return "parsed"
        except Exception as error:
            self.repository.update_stage(self.db, resume_id, "failed", str(error).split(":", 1)[0])
            self.repository.record_attempt(
                self.db,
                resume_id,
                "parse",
                "failed",
                error_code=str(error).split(":", 1)[0],
            )
            return "failed"

    def score_candidate(
        self,
        candidate_id: str,
        requirements: JobRequirements,
        client: ScoringClient,
        embedding_context: str = "",
    ) -> MatchResult:
        candidate = self.repository.get_candidate(self.db, candidate_id)
        if candidate is None or candidate.resume_file is None:
            raise ValueError("CANDIDATE_NOT_FOUND")
        resume_record = candidate.resume_file
        with _score_lock:
            existing_match = self.repository.get_match(self.db, candidate_id)
            if existing_match is not None:
                return MatchResult.model_validate(existing_match.result_json)
            if resume_record.parsed_json is None:
                raise ValueError("RESUME_NOT_PARSED")
            resume = ExtractedResume.model_validate(resume_record.parsed_json)
            self.repository.record_attempt(self.db, resume_record.id, "score", "started")
            try:
                result = score_match(requirements, resume, embedding_context, client)
            except Exception as error:
                self.repository.record_attempt(
                    self.db,
                    resume_record.id,
                    "score",
                    "failed",
                    error_code=type(error).__name__,
                )
                raise
            if result.candidate_id != candidate_id:
                self.repository.record_attempt(
                    self.db,
                    resume_record.id,
                    "score",
                    "failed",
                    error_code="CANDIDATE_ID_MISMATCH",
                )
                raise ValueError("CANDIDATE_ID_MISMATCH")
            self.repository.save_match(self.db, candidate_id, result)
            self.repository.record_attempt(self.db, resume_record.id, "score", "completed")
            self.repository.update_stage(self.db, resume_record.id, "scored")
            return result


def process_resume(worker: ResumeWorker, resume_id: str) -> str:
    return worker.process_resume(resume_id)


def score_candidate(
    worker: ResumeWorker,
    candidate_id: str,
    requirements: JobRequirements,
    client: ScoringClient,
    embedding_context: str = "",
) -> MatchResult:
    return worker.score_candidate(candidate_id, requirements, client, embedding_context)


def process_batch(worker: ResumeWorker, resume_ids: list[str]) -> Mapping[str, str]:
    statuses: dict[str, str] = {}
    for resume_id in resume_ids:
        try:
            statuses[resume_id] = worker.process_resume(resume_id)
        except Exception:
            statuses[resume_id] = "failed"
    return statuses


class LocalTaskQueue:
    """Small local queue adapter; production deployments can replace it with Redis/Celery."""

    def __init__(self) -> None:
        self._pending: deque[Callable[[], object]] = deque()

    def enqueue(self, task: Callable[[], object]) -> None:
        self._pending.append(task)

    def run_next(self) -> object | None:
        if not self._pending:
            return None
        return self._pending.popleft()()

    def pending_count(self) -> int:
        return len(self._pending)
