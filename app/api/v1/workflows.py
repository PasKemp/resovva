"""API v1 – Workflows: Startet/Resume LangGraph Runs."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.graph import build_graph
from app.agents.state import AgentState

router = APIRouter(prefix="/workflows", tags=["workflows"])

# Einmaliges Kompilieren beim Start der App (Performance)
agent_app = build_graph()

class WorkflowRequest(BaseModel):
    case_id: str

@router.post("/run")
async def run_workflow(request: WorkflowRequest):
    """Startet den Agenten für einen Case."""
    case_id = request.case_id

    # Config für Checkpointer: Case ID = Thread ID
    config = {"configurable": {"thread_id": case_id}}

    # Initialer State
    initial_state = {
        "case_id": case_id,
        "messages": [],
        "documents": [],
        "missing_info": [],
        "dossier_ready": False,
        "payment_status": "pending"
    }

    try:
        # Wir rufen invoke auf. Da unsere Nodes async sind, 'await'en wir das Ergebnis.
        # Im echten Betrieb evtl. 'ainvoke' nutzen.
        result = await agent_app.ainvoke(initial_state, config=config)

        return {
            "status": "success",
            "current_step": result.get("current_step"),
            "documents_found": len(result.get("documents", [])),
            # Gib nur die letzte Message zurück, nicht den ganzen Roman
            "last_message": result.get("messages")[-1] if result.get("messages") else None
        }
    except Exception as e:
        # Logging wäre hier gut
        raise HTTPException(status_code=500, detail=f"Workflow Error: {str(e)}")

@router.post("/resume")
async def resume_workflow():
    return {"status": "placeholder"}
