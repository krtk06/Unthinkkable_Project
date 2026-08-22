from fastapi import FastAPI

from app.domain.resume import ExtractedResume

app = FastAPI(title="Smart Resume Screener", version="0.1.0")


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/schemas/extracted-resume", tags=["schemas"])
def extracted_resume_schema() -> dict[str, object]:
    return ExtractedResume.model_json_schema()
