"""
Workflows Router.

Low-level orchestration for LangGraph agents.
Provides generic 'run' and 'resume' capabilities to handle stateful transitions
manually if needed (primary orchestration happens via Case Router).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.api.v1.schemas.workflows import ResumeRequest, WorkflowRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])


# ── Workflow Control Endpoints ───────────────────────────────────────────────

@router.post("/run")
async def run_workflow(request: WorkflowRequest) -> dict:
    """
    Start the case agent graph directly from its initial state.

    Args:
        request: Identification of the case thread.

    Returns:
        dict: Final state summary.

    Raises:
        HTTPException: If the graph invocation fails (500).
    """
    from app.agents.graph import get_agent_app

    case_id = request.case_id
    config = {"configurable": {"thread_id": case_id}}
    
    # Initialize state with default schema
    initial_state = {
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
        agent_app = await get_agent_app()
        result = await agent_app.ainvoke(initial_state, config=config)
        
        return {
            "status": "success",
            "current_step": result.get("current_step"),
            "last_message": result.get("messages", [None])[-1],
        }
    except Exception as exc:
        logger.error(
            "Workflow invocation failed",
            extra={"case_id": case_id, "error": str(exc)},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Workflow error: {str(exc)}"
        )


@router.post("/resume")
async def resume_workflow(request: ResumeRequest) -> dict:
    """
    Resume a paused LangGraph thread (Human-in-the-Loop).

    Updates the agent state with user-provided corrections and triggers
    automatic continuation.

    Args:
        request: The case thread ID and entity updates.

    Returns:
        dict: Success indicator.

    Raises:
        HTTPException: If the resume operation fails (500).
    """
    from app.agents.graph import get_agent_app

    case_id = request.case_id
    config = {"configurable": {"thread_id": case_id}}
    
    confirmed_update = {
        "meter_number": request.meter_number,
        "malo_id": request.malo_id,
        "dispute_amount": request.dispute_amount,
        "network_operator": request.network_operator,
    }

    try:
        agent_app = await get_agent_app()
        # 1. Update the interrupt-stopped state
        await agent_app.aupdate_state(config, confirmed_update)
        # 2. Trigger non-input invoke to resume from current checkpoint
        await agent_app.ainvoke(None, config=config)
        
        return {"status": "resumed", "case_id": case_id}
    except Exception as exc:
        logger.error(
            "Agent resume failed",
            extra={"case_id": case_id, "error": str(exc)},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Resume failed: {str(exc)}"
        )
