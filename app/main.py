from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.domain.resume import ExtractedResume

app = FastAPI(title="Smart Resume Screener", version="0.1.0")
app.include_router(api_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exception: HTTPException) -> JSONResponse:
    detail = exception.detail
    return JSONResponse(status_code=exception.status_code, content=detail)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/schemas/extracted-resume", tags=["schemas"])
def extracted_resume_schema() -> dict[str, object]:
    return ExtractedResume.model_json_schema()
