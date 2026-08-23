from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.domain.resume import ExtractedResume

app = FastAPI(title="Smart Resume Screener", version="0.1.0")
app.include_router(api_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exception: HTTPException) -> JSONResponse:
    detail = exception.detail
    return JSONResponse(status_code=exception.status_code, content=detail)


@app.exception_handler(RequestValidationError)
async def request_validation_handler(_: Request, exception: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "REQUEST_VALIDATION_FAILED",
                "message": "Request validation failed",
                "details": exception.errors(),
            }
        },
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(_: Request, exception: RuntimeError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": str(exception),
                "message": "Service unavailable",
                "details": {},
            }
        },
    )


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/schemas/extracted-resume", tags=["schemas"])
def extracted_resume_schema() -> dict[str, object]:
    return ExtractedResume.model_json_schema()
