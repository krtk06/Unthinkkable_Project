from app.domain.resume import Candidate, Contact, ExtractedResume
from app.matching.embeddings import (
    NullEmbeddingClient,
    build_candidate_text,
    embedding_cache_key,
)


def test_build_candidate_text_contains_searchable_resume_facts() -> None:
    resume = ExtractedResume.model_validate(
        {
            "schema_version": "1.0",
            "candidate": Candidate(
                name="Ada",
                contact=Contact(email=None, phone=None, url=None),
                location="London",
            ),
            "skills": ["Python", "APIs"],
            "experience": [],
            "education": [],
            "certifications": [],
            "languages": [],
            "warnings": [],
        }
    )

    text = build_candidate_text(resume)

    assert "Python" in text
    assert "APIs" in text
    assert "London" in text
    assert "ada@example.com" not in text


def test_embedding_cache_key_changes_with_content_and_model() -> None:
    first = embedding_cache_key("Python APIs", "model-a", "v1")

    assert first != embedding_cache_key("Python APIs changed", "model-a", "v1")
    assert first != embedding_cache_key("Python APIs", "model-b", "v1")
    assert first == embedding_cache_key("Python APIs", "model-a", "v1")


def test_null_embedding_client_is_safe_for_local_small_batches() -> None:
    assert NullEmbeddingClient().embed("resume") == []
