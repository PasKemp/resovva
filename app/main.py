"""FastAPI Application – Resovva.ai."""

from fastapi import FastAPI

from app.api.v1 import documents, workflows

app = FastAPI(
    title="Resovva.ai",
    description="Intelligenter Fall-Assistent (LegalTech)",
    version="0.1.0",
)

app.include_router(workflows.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
