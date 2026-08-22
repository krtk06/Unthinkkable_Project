from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return uuid4().hex


def now_utc() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class ScreeningSession(Base):
    __tablename__ = "screening_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String(32), default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )
    job_description: Mapped["JobDescription | None"] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )
    candidates: Mapped[list["Candidate"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("screening_sessions.id", ondelete="CASCADE"), unique=True
    )
    raw_text: Mapped[str] = mapped_column(Text)
    normalized_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    session: Mapped[ScreeningSession] = relationship(back_populates="job_description")


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("screening_sessions.id", ondelete="CASCADE"), index=True
    )
    session: Mapped[ScreeningSession] = relationship(back_populates="candidates")
    resume_file: Mapped["ResumeFile"] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", uselist=False
    )
    match: Mapped["Match | None"] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", uselist=False
    )


class ResumeFile(Base):
    __tablename__ = "resume_files"
    __table_args__ = (
        UniqueConstraint("session_id", "checksum", name="uq_resume_session_checksum"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("screening_sessions.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), unique=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int]
    checksum: Mapped[str] = mapped_column(String(64))
    storage_uri: Mapped[str] = mapped_column(String(512))
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(nullable=True)
    ocr_used: Mapped[bool | None] = mapped_column(nullable=True)
    extraction_warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    extraction_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    extraction_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    extraction_prompt_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    parsed_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )
    candidate: Mapped[Candidate] = relationship(back_populates="resume_file")
    attempts: Mapped[list["ProcessingAttempt"]] = relationship(
        back_populates="resume_file", cascade="all, delete-orphan"
    )


class ProcessingAttempt(Base):
    __tablename__ = "processing_attempts"
    __table_args__ = (
        UniqueConstraint(
            "resume_file_id", "stage", "attempt_number", name="uq_processing_attempt_number"
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    resume_file_id: Mapped[str] = mapped_column(
        ForeignKey("resume_files.id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt_number: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    resume_file: Mapped[ResumeFile] = relationship(back_populates="attempts")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), unique=True
    )
    score: Mapped[int]
    required_coverage: Mapped[float]
    preferred_coverage: Mapped[float]
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    provider: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(160))
    prompt_version: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    candidate: Mapped[Candidate] = relationship(back_populates="match")
