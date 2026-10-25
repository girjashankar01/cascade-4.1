"""Stage 0 health endpoint; application workflows are added in later stages."""

from fastapi import FastAPI

app = FastAPI(title="DAO Accountability Engine", version="0.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
