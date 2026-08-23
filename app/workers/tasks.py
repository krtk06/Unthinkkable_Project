from collections import deque
from collections.abc import Callable, Mapping
from threading import Lock
from typing import Protocol

from app.db.mongo_repository import MongoResumeRepository
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
        repository: MongoResumeRepository,
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
        self.repository = repository
        self.storage = storage
        self.extractor = extractor
        self.parser = parser
        self.provider = provider
        self.model = model
        self.prompt_version = prompt_version
        self.embedding_client = embedding_client
        self.embedding_model = embedding_model

    def process_resume(self, candidate_id: str) -> str:
        candidate = self.repository.get_candidate(candidate_id)
        if candidate is None:
            raise ValueError("CANDIDATE_NOT_FOUND")
        resume = candidate["resume"]
        status = str(resume["status"])
        if status in {"parsed", "scored"}:
            return status
        if not self.repository.claim_stage(candidate_id, ["uploaded", "failed"], "processing"):
            current = self.repository.get_candidate(candidate_id)
            return str(current["resume"]["status"]) if current is not None else "failed"
        self.repository.record_attempt(candidate_id, "parse", "started")
        try:
            extraction = self.extractor.extract(
                self.storage.get_original(resume["storage_uri"]), resume["content_type"]
            )
            self.repository.update_stage(candidate_id, "text_extracted")
            parsed = self.parser.extract_resume(extraction.text)
            self.repository.save_extraction(
                candidate_id,
                text=extraction.text,
                page_count=extraction.page_count,
                ocr_used=extraction.ocr_used,
                warnings=extraction.warnings,
                parsed=parsed.model_dump(mode="json"),
                provenance={
                    "provider": self.provider,
                    "model": self.model,
                    "prompt_version": self.prompt_version,
                },
            )
            if self.embedding_client is not None:
                self.repository.save_embedding(
                    candidate_id,
                    embed_candidate(parsed, self.embedding_client),
                    self.embedding_model,
                )
            return "parsed"
        except Exception as error:
            code = type(error).__name__
            self.repository.update_stage(candidate_id, "failed", code)
            self.repository.record_attempt(candidate_id, "parse", "failed", error_code=code)
            return "failed"

    def score_candidate(
        self,
        candidate_id: str,
        requirements: JobRequirements,
        client: ScoringClient,
        embedding_context: str = "",
    ) -> MatchResult:
        candidate = self.repository.get_candidate(candidate_id)
        if candidate is None:
            raise ValueError("CANDIDATE_NOT_FOUND")
        with _score_lock:
            existing_match = self.repository.get_match(candidate_id)
            if existing_match is not None:
                return MatchResult.model_validate(existing_match)
            if not self.repository.claim_stage(candidate_id, ["parsed"], "scoring"):
                raise ValueError("SCORING_IN_PROGRESS")
            parsed = candidate["resume"].get("parsed_json")
            if parsed is None:
                raise ValueError("RESUME_NOT_PARSED")
            resume = ExtractedResume.model_validate(parsed)
            self.repository.record_attempt(candidate_id, "score", "started")
            try:
                result = score_match(requirements, resume, embedding_context, client)
                if result.candidate_id != candidate_id:
                    raise ValueError("CANDIDATE_ID_MISMATCH")
                if not self.repository.save_match(candidate_id, result.model_dump(mode="json")):
                    existing = self.repository.get_match(candidate_id)
                    if existing is None:
                        raise ValueError("MATCH_SAVE_FAILED")
                    return MatchResult.model_validate(existing)
                self.repository.record_attempt(candidate_id, "score", "completed")
                return result
            except Exception as error:
                self.repository.record_attempt(
                    candidate_id, "score", "failed", error_code=type(error).__name__
                )
                raise


def process_resume(worker: ResumeWorker, candidate_id: str) -> str:
    return worker.process_resume(candidate_id)


def score_candidate(
    worker: ResumeWorker,
    candidate_id: str,
    requirements: JobRequirements,
    client: ScoringClient,
    embedding_context: str = "",
) -> MatchResult:
    return worker.score_candidate(candidate_id, requirements, client, embedding_context)


def process_batch(worker: ResumeWorker, candidate_ids: list[str]) -> Mapping[str, str]:
    statuses: dict[str, str] = {}
    for candidate_id in candidate_ids:
        try:
            statuses[candidate_id] = worker.process_resume(candidate_id)
        except Exception:
            statuses[candidate_id] = "failed"
    return statuses


class LocalTaskQueue:
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
