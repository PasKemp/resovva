"""
API v1 – Workflows: Startet/Resume LangGraph Runs.

Endpoints z.B.:
- POST /api/v1/workflows/run   – Fall starten (Graph ausführen)
- POST /api/v1/workflows/resume – Nach User-Input (Gap) fortsetzen
"""

from fastapi import APIRouter

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("/run")
async def run_workflow():
    """Startet einen neuen LangGraph-Workflow für einen Fall."""
    # TODO: case_id aus Auth/Request, Graph invoken
    return {"status": "pending", "message": "Workflow run – placeholder"}


@router.post("/resume")
async def resume_workflow():
    """Setzt einen pausierten Workflow fort (z.B. nach Gap-Analysis-Input)."""
    # TODO: thread_id / run_id, User-Input, Graph resume
    return {"status": "resumed", "message": "Workflow resume – placeholder"}
