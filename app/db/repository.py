from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Candidate, Match, ResumeFile, ScreeningSession
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

    def delete_session(self, db: Session, session_id: str) -> None:
        record = db.get(ScreeningSession, session_id)
        if record is None:
            return
        db.delete(record)
        db.commit()
