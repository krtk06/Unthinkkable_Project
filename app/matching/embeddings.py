import hashlib
from typing import Protocol

from app.domain.resume import ExtractedResume


class EmbeddingClient(Protocol):
    def embed(self, text: str) -> list[float]:
        """Return a vector for semantic retrieval."""


class NullEmbeddingClient:
    def embed(self, text: str) -> list[float]:
        return []


def embed_candidate(resume: ExtractedResume, client: EmbeddingClient) -> list[float]:
    return client.embed(build_candidate_text(resume))


def build_candidate_text(resume: ExtractedResume) -> str:
    sections = [
        f"Location: {resume.candidate.location or ''}",
        "Skills: " + ", ".join(resume.skills),
    ]
    for experience in resume.experience:
        sections.append(f"Role: {experience.role or ''} at {experience.company or ''}")
        sections.append(experience.description)
    for education in resume.education:
        sections.append(
            f"Education: {education.degree or ''} {education.field or ''} "
            f"at {education.institution or ''}"
        )
    sections.extend(
        f"Certification: {certification.name}" for certification in resume.certifications
    )
    return "\n".join(section for section in sections if section.strip())


def embedding_cache_key(text: str, model: str, version: str) -> str:
    content = f"{version}\0{model}\0{text}".encode()
    return hashlib.sha256(content).hexdigest()
