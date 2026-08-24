from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import Lock
from typing import Protocol, cast

from app.db.mongo_repository import MongoResumeRepository
from app.domain.job import JobRequirements
from app.domain.match import MatchResult, ModelMetadata
from app.domain.resume import ExtractedResume
from app.ingestion.text_extract import ExtractionResult
from app.matching.embeddings import (
    EmbeddingClient,
    build_candidate_text,
    build_jd_text,
    cosine_similarity,
    embed_candidate,
    lexical_skill_similarity,
)
from app.matching.scoring import ScoringClient
from app.matching.scoring import score_candidate as score_match
from app.workers.queue import AtlasTaskQueue

_score_lock = Lock()


class FileStorage(Protocol):
    def get_original(self, uri: str) -> bytes: ...


class TextExtractor(Protocol):
    def extract(self, file_bytes: bytes, content_type: str) -> ExtractionResult: ...


class ResumeParser(Protocol):
    def extract_resume(self, text: str) -> ExtractedResume: ...


@dataclass
class ModelConfig:
    provider: str
    model: str
    prompt_version: str


@dataclass
class EmbeddingConfig:
    client: EmbeddingClient | None = None
    model: str = ""
    threshold: float = 7.0


class ResumeWorker:
    def __init__(
        self,
        repository: MongoResumeRepository,
        storage: FileStorage,
        extractor: TextExtractor,
        parser: ResumeParser,
        *,
        model_config: ModelConfig,
        embedding_config: EmbeddingConfig | None = None,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.extractor = extractor
        self.parser = parser
        self.provider = model_config.provider
        self.model = model_config.model
        self.prompt_version = model_config.prompt_version
        _emb = embedding_config or EmbeddingConfig()
        self.embedding_client = _emb.client
        self.embedding_model = _emb.model
        self.shortlist_threshold = _emb.threshold

    def process_resume(self, candidate_id: str) -> str:
        candidate = self.repository.get_candidate(candidate_id)
        if candidate is None:
            raise ValueError("CANDIDATE_NOT_FOUND")
        resume = candidate["resume"]
        status = str(resume["status"])
        if status in {"parsed", "scored", "score_failed"}:
            return status
        if not self.repository.claim_stage(
            candidate_id, ["queued", "uploaded", "failed"], "processing"
        ):
            current = self.repository.get_candidate(candidate_id)
            return str(current["resume"]["status"]) if current is not None else "failed"
        self.repository.record_attempt(candidate_id, "parse", "started")
        try:
            extraction = self.extractor.extract(
                self.storage.get_original(resume["storage_uri"]), resume["content_type"]
            )
            self.repository.update_stage(candidate_id, "text_extracted")
            parsed = self.parser.extract_resume(extraction.text)
            from app.db.mongo_repository import ExtractionPayload

            self.repository.save_extraction(
                candidate_id,
                ExtractionPayload(
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
                ),
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
            if not self.repository.claim_stage(candidate_id, ["parsed", "score_failed"], "scoring"):
                raise ValueError("SCORING_IN_PROGRESS")
            parsed = candidate["resume"].get("parsed_json")
            if parsed is None:
                raise ValueError("RESUME_NOT_PARSED")
            resume = ExtractedResume.model_validate(parsed)
            self.repository.record_attempt(candidate_id, "score", "started")
            try:
                similarity = self._semantic_similarity(requirements, resume)
                context = f"similarity:{similarity:.1f}"
                result = score_match(
                    requirements,
                    resume,
                    context,
                    client,
                    model=ModelMetadata(
                        provider=self.provider,
                        model=self.model,
                        prompt_version=self.prompt_version,
                    ),
                    shortlist_threshold=self.shortlist_threshold,
                )
                result = result.model_copy(update={"candidate_id": candidate_id})
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
                self.repository.update_stage(candidate_id, "score_failed", type(error).__name__)
                raise

    def _semantic_similarity(
        self, requirements: JobRequirements, resume: ExtractedResume
    ) -> float:
        if self.embedding_client is not None:
            jd_vector = self.embedding_client.embed(build_jd_text(requirements))
            candidate_vector = self.embedding_client.embed(build_candidate_text(resume))
            if jd_vector and candidate_vector:
                return cosine_similarity(jd_vector, candidate_vector)
        return lexical_skill_similarity(requirements, resume)


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


def process_candidate_job(worker: ResumeWorker, candidate_id: str) -> None:
    status = worker.process_resume(candidate_id)
    if status == "failed":
        raise RuntimeError("RESUME_PROCESSING_FAILED")
    if status == "scored":
        return
    candidate = worker.repository.get_candidate(candidate_id)
    if candidate is None:
        return
    session = worker.repository.get_session(candidate["session_id"])
    normalized = ((session or {}).get("job_description") or {}).get("normalized_json")
    if normalized:
        worker.score_candidate(
            candidate_id,
            JobRequirements.model_validate(normalized),
            cast(ScoringClient, worker.parser),
        )


def run_once(queue: AtlasTaskQueue, worker: ResumeWorker, worker_id: str) -> bool:
    job = queue.claim(worker_id)
    if job is None:
        return False
    try:
        if job["task"] != "process_candidate":
            raise ValueError("UNKNOWN_TASK")
        process_candidate_job(worker, job["payload"]["candidate_id"])
        queue.complete(job["_id"])
    except Exception as error:
        queue.fail(job["_id"], type(error).__name__)
    return True
