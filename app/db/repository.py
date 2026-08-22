from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Candidate, Match, ProcessingAttempt, ResumeFile, ScreeningSession
from app.domain.match import MatchResult


class ResumeRepository:
    def create_session(self, db: Session) -> ScreeningSession:
        record = ScreeningSession()
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def add_resume(
        self,
        db: Session,
        session_id: str,
        *,
        filename: str,
        content_type: str,
        size_bytes: int,
        checksum: str,
        storage_uri: str,
    ) -> ResumeFile:
        candidate = Candidate(session_id=session_id)
        resume = ResumeFile(
            session_id=session_id,
            candidate=candidate,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            checksum=checksum,
            storage_uri=storage_uri,
        )
        db.add(resume)
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            raise ValueError("DUPLICATE_RESUME") from error
        db.refresh(resume)
        return resume

    def update_stage(
        self, db: Session, resume_id: str, status: str, error_code: str | None = None
    ) -> None:
        resume = self.get_resume(db, resume_id)
        if resume is None:
            raise ValueError("RESUME_NOT_FOUND")
        resume.status = status
        resume.error_code = error_code
        db.commit()

    def save_parsed_resume(self, db: Session, resume_id: str, parsed: dict[str, Any]) -> None:
        resume = self.get_resume(db, resume_id)
        if resume is None:
            raise ValueError("RESUME_NOT_FOUND")
        resume.parsed_json = parsed
        resume.status = "parsed"
        db.commit()

    def save_extraction(
        self,
        db: Session,
        resume_id: str,
        *,
        text: str,
        page_count: int,
        ocr_used: bool,
        warnings: list[str],
        parsed: dict[str, Any],
        provider: str,
        model: str,
        prompt_version: str,
    ) -> None:
        resume = self.get_resume(db, resume_id)
        if resume is None:
            raise ValueError("RESUME_NOT_FOUND")
        resume.extracted_text = text
        resume.page_count = page_count
        resume.ocr_used = ocr_used
        resume.extraction_warnings = warnings
        resume.extraction_provider = provider
        resume.extraction_model = model
        resume.extraction_prompt_version = prompt_version
        resume.parsed_json = parsed
        resume.status = "parsed"
        db.commit()

    def record_attempt(
        self,
        db: Session,
        resume_id: str,
        stage: str,
        status: str,
        *,
        attempt_number: int | None = None,
        error_code: str | None = None,
    ) -> ProcessingAttempt:
        resume = self.get_resume(db, resume_id)
        if resume is None:
            raise ValueError("RESUME_NOT_FOUND")
        for _ in range(3):
            if attempt_number is None:
                latest_attempt = db.scalar(
                    select(func.max(ProcessingAttempt.attempt_number)).where(
                        ProcessingAttempt.resume_file_id == resume_id,
                        ProcessingAttempt.stage == stage,
                    )
                )
                next_attempt_number = (latest_attempt or 0) + 1
            else:
                next_attempt_number = attempt_number
            if next_attempt_number < 1:
                raise ValueError("INVALID_ATTEMPT_NUMBER")
            attempt = ProcessingAttempt(
                resume_file_id=resume_id,
                stage=stage,
                status=status,
                attempt_number=next_attempt_number,
                error_code=error_code,
            )
            db.add(attempt)
            try:
                db.commit()
            except IntegrityError as error:
                db.rollback()
                if attempt_number is not None:
                    raise ValueError("ATTEMPT_NUMBER_CONFLICT") from error
                continue
            db.refresh(attempt)
            return attempt
        raise ValueError("ATTEMPT_NUMBER_CONFLICT")

    def save_match(self, db: Session, candidate_id: str, result: MatchResult) -> Match:
        match = Match(
            candidate_id=candidate_id,
            score=result.score,
            required_coverage=result.required_coverage,
            preferred_coverage=result.preferred_coverage,
            result_json=result.model_dump(mode="json"),
            provider=result.model.provider,
            model=result.model.model,
            prompt_version=result.model.prompt_version,
        )
        db.add(match)
        db.commit()
        db.refresh(match)
        return match

    def get_resume(self, db: Session, resume_id: str) -> ResumeFile | None:
        return db.scalar(select(ResumeFile).where(ResumeFile.id == resume_id))

    def delete_session(self, db: Session, session_id: str, *, storage: Any | None = None) -> None:
        record = db.get(ScreeningSession, session_id)
        if record is None:
            return
        if storage is not None:
            for candidate in record.candidates:
                if candidate.resume_file is not None:
                    uri = candidate.resume_file.storage_uri
                    still_referenced = db.scalar(
                        select(ResumeFile.id).where(
                            ResumeFile.storage_uri == uri,
                            ResumeFile.session_id != session_id,
                        )
                    )
                    if still_referenced is None:
                        storage.delete_original(uri)
        db.delete(record)
        db.commit()
