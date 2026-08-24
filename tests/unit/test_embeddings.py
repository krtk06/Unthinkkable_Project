import pytest

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


def test_openai_embedding_client_returns_vector(monkeypatch: "pytest.MonkeyPatch") -> None:
    import sys

    from app.matching.embeddings import OpenAIEmbeddingClient

    class FakeEmbeddings:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def create(self, *, model: str, input: str) -> object:
            self.calls.append((model, input))
            return type(
                "Resp",
                (),
                {"data": [type("D", (), {"embedding": [0.1, 0.2, 0.3]})()]},
            )()

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.embeddings = FakeEmbeddings()

    fake_module = type("openai", (), {"OpenAI": FakeOpenAI})
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    client = OpenAIEmbeddingClient(api_key="test", model="text-embedding-3-small")
    vector = client.embed("Python APIs")
    assert vector == [0.1, 0.2, 0.3]


def test_openai_embedding_client_falls_back_to_empty_on_error(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    import sys

    from app.matching.embeddings import OpenAIEmbeddingClient

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.embeddings = type(
                "E",
                (),
                {
                    "create": lambda self, **kw: (_ for _ in ()).throw(
                        RuntimeError("down")
                    )
                },
            )()

    fake_module = type("openai", (), {"OpenAI": FakeOpenAI})
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    client = OpenAIEmbeddingClient(api_key="test", model="m")
    assert client.embed("resume") == []
