from fastapi import FastAPI

app = FastAPI(title="Smart Resume Screener", version="0.1.0")


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok"}
