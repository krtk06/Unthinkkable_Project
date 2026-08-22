"""Create the initial resume screening schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "screening_sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "job_descriptions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(32),
            sa.ForeignKey("screening_sessions.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("normalized_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "candidates",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(32),
            sa.ForeignKey("screening_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index("ix_candidates_session_id", "candidates", ["session_id"])
    op.create_table(
        "resume_files",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(32),
            sa.ForeignKey("screening_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            sa.String(32),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("storage_uri", sa.String(512), nullable=False),
        sa.Column("extracted_text", sa.Text, nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("ocr_used", sa.Boolean, nullable=True),
        sa.Column("extraction_warnings", sa.JSON, nullable=True),
        sa.Column("extraction_provider", sa.String(80), nullable=True),
        sa.Column("extraction_model", sa.String(160), nullable=True),
        sa.Column("extraction_prompt_version", sa.String(80), nullable=True),
        sa.Column("embedding", sa.JSON, nullable=True),
        sa.Column("embedding_model", sa.String(160), nullable=True),
        sa.Column("parsed_json", sa.JSON, nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "checksum", name="uq_resume_session_checksum"),
    )
    op.create_index("ix_resume_files_session_id", "resume_files", ["session_id"])
    op.create_table(
        "processing_attempts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "resume_file_id",
            sa.String(32),
            sa.ForeignKey("resume_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("attempt_number", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "resume_file_id", "stage", "attempt_number", name="uq_processing_attempt_number"
        ),
    )
    op.create_index(
        "ix_processing_attempts_resume_file_id", "processing_attempts", ["resume_file_id"]
    )
    op.create_table(
        "matches",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(32),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("required_coverage", sa.Float, nullable=False),
        sa.Column("preferred_coverage", sa.Float, nullable=False),
        sa.Column("result_json", sa.JSON, nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("model", sa.String(160), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("matches")
    op.drop_index("ix_processing_attempts_resume_file_id", table_name="processing_attempts")
    op.drop_table("processing_attempts")
    op.drop_index("ix_resume_files_session_id", table_name="resume_files")
    op.drop_table("resume_files")
    op.drop_index("ix_candidates_session_id", table_name="candidates")
    op.drop_table("candidates")
    op.drop_table("job_descriptions")
    op.drop_table("screening_sessions")
