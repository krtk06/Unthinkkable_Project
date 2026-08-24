import hashlib
import math
from typing import Protocol

from app.config import get_settings
from app.domain.job import JobRequirements
from app.domain.resume import ExtractedResume


class EmbeddingClient(Protocol):
    def embed(self, text: str) -> list[float]:
        """Return a vector for semantic retrieval."""


class NullEmbeddingClient:
    def embed(self, text: str) -> list[float]:
        return []


class OpenAIEmbeddingClient:
    """OpenAI embeddings-backed client. Falls back to an empty vector on any
    error so scoring degrades to the lexical similarity instead of failing."""

    def __init__(self, api_key: str, model: str) -> None:
        from openai import OpenAI

        settings = get_settings()
        self.client = OpenAI(api_key=api_key, timeout=settings.llm_timeout)
        self.model = model

    def embed(self, text: str) -> list[float]:
        try:
            response = self.client.embeddings.create(
                model=self.model, input=text
            )
            return response.data[0].embedding
        except Exception:
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


def job_skill_names(requirements: JobRequirements) -> list[str]:
    names = [requirement.name for requirement in requirements.required]
    names.extend(requirement.name for requirement in requirements.preferred)
    return names


def lexical_skill_similarity(requirements: JobRequirements, resume: ExtractedResume) -> float:
    """Jaccard-style overlap between JD skills and resume skills, scaled to 0-10."""
    jd_skills = {name.lower() for name in job_skill_names(requirements)}
    resume_skills = {skill.lower() for skill in resume.skills}
    if not jd_skills or not resume_skills:
        return 0.0
    intersection = jd_skills & resume_skills
    union = jd_skills | resume_skills
    return round(10.0 * len(intersection) / len(union), 1)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Cosine similarity mapped to 0-10. Empty vectors return 0.0."""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if norm_left == 0 or norm_right == 0:
        return 0.0
    cosine = dot / (norm_left * norm_right)
    return round(max(0.0, min(1.0, cosine)) * 10.0, 1)


def build_jd_text(requirements: JobRequirements) -> str:
    sections = [f"Title: {requirements.title or ''}"]
    sections.append("Skills: " + ", ".join(job_skill_names(requirements)))
    sections.extend(requirements.responsibilities)
    return "\n".join(section for section in sections if section.strip())
