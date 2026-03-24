"""
Workflows Router – LangGraph-Run & Resume.

POST /workflows/run    – Startet den Agenten direkt (Legacy-Endpunkt)
POST /workflows/resume – Setzt einen pausierten Graphen fort (US-3.5)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowRequest(BaseModel):
    case_id: str


class ResumeRequest(BaseModel):
    case_id: str
    meter_number: str | None = None
    malo_id: str | None = None
    dispute_amount: float | None = None
    network_operator: str | None = None


@router.post("/run")
async def run_workflow(request: WorkflowRequest):
    """Startet den Agenten direkt (verwendet von /cases/{id}/analyze bevorzugt)."""
    from app.agents.graph import get_agent_app

    case_id = request.case_id
    config = {"configurable": {"thread_id": case_id}}
    initial_state: dict = {
        "case_id": case_id,
        "messages": [],
        "documents": [],
        "extracted_entities": {},
        "meter_number": None,
        "malo_id": None,
        "dispute_amount": None,
        "currency": None,
        "network_operator": None,
        "chronology": [],
        "missing_info": [],
        "dossier_ready": False,
        "payment_status": "pending",
    }
    try:
        result = await (await get_agent_app()).ainvoke(initial_state, config=config)
        return {
            "status": "success",
            "current_step": result.get("current_step"),
            "last_message": result.get("messages", [None])[-1],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workflow-Fehler: {exc}")


@router.post("/resume")
async def resume_workflow(request: ResumeRequest):
    """
    Setzt einen pausierten LangGraph-Lauf fort (US-3.5 Human-in-the-Loop).

    Aktualisiert den gespeicherten State mit den bestätigten Nutzerdaten
    und ruft _node_confirm auf.
    """
    from app.agents.graph import get_agent_app

    config = {"configurable": {"thread_id": request.case_id}}
    confirmed_update = {
        "meter_number": request.meter_number,
        "malo_id": request.malo_id,
        "dispute_amount": request.dispute_amount,
        "network_operator": request.network_operator,
    }
    try:
        agent_app = await get_agent_app()
        await agent_app.aupdate_state(config, confirmed_update)
        await agent_app.ainvoke(None, config=config)
        return {"status": "resumed", "case_id": request.case_id}
    except Exception as exc:
        logger.error("Resume fehlgeschlagen (Case %s): %s", request.case_id, exc)
        raise HTTPException(status_code=500, detail=f"Resume fehlgeschlagen: {exc}")
