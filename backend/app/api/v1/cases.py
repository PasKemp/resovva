"""
Cases Router.

Handles case lifecycle management including listing, creation, deletion,
and the asynchronous AI analysis process (LangGraph).
Supports human-in-the-loop (HiTL) interactions for entity correction.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, get_owned_case
from app.api.v1.schemas.cases import (
    AnalysisResultResponse,
    CaseAnalyzeResponse,
    CaseCreateResponse,
    CaseDeleteResponse,
    CaseListResponse,
    CaseStatusResponse,
    CaseSummary,
    ConfirmAnalysisRequest,
    ConfirmAnalysisResponse,
    ExtractionFieldResponse,
    ExtractionResultResponse,
    OpponentResponse,
    UpdateOpponentRequest,
    UpdateOpponentResponse,
)
from app.domain.models.db import Case
from app.infrastructure.database import get_db
from app.infrastructure.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["cases"])

# ── Configuration ─────────────────────────────────────────────────────────────

CONFIDENCE_THRESHOLD: float = 0.8


# ── Case Lifecycle Endpoints ──────────────────────────────────────────────────

@router.get("", response_model=CaseListResponse)
def list_cases(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> CaseListResponse:
    """
    List all cases belonging to the authenticated user.

    Used by the main dashboard.

    Returns:
        CaseListResponse: List of cases sorted by creation date (newest first).
    """
    cases = (
        db.query(Case)
        .filter(Case.user_id == current_user.id)
        .order_by(Case.created_at.desc())
        .all()
    )

    return CaseListResponse(
        cases=[
            CaseSummary(
                case_id=str(c.id),
                created_at=c.created_at.isoformat(),
                status=c.status,
                network_operator=(c.extracted_data or {}).get("network_operator"),
                document_count=len(c.documents),
            )
            for c in cases
        ]
    )


@router.post("", status_code=201, response_model=CaseCreateResponse)
def create_case(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> CaseCreateResponse:
    """
    Create a new empty case (Initial DRAFT state).

    Returns:
        CaseCreateResponse: The ID and status of the new case.
    """
    case = Case(
        user_id=current_user.id,
        status="DRAFT",
        extracted_data={},
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    logger.info(
        "New case created",
        extra={"case_id": str(case.id), "user_id": str(current_user.id)}
    )

    return CaseCreateResponse(
        case_id=str(case.id),
        status=case.status,
        message="Case created successfully.",
    )


@router.delete("/{case_id}", response_model=CaseDeleteResponse)
def delete_case(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> CaseDeleteResponse:
    """
    Permanently delete a case and all associated data (GDPR Hard-Delete).

    Cleanup Order: S3 Storage -> Qdrant (Vectors) -> PostgreSQL (Cascaded).

    Args:
        case_id: UUID of the case to delete.

    Returns:
        CaseDeleteResponse: Confirmation message.

    Raises:
        HTTPException: If the case is not found or owned by another user (404).
    """
    case = get_owned_case(case_id, current_user, db)

    # 1. External Cleanup
    _delete_from_storage(case)
    _delete_from_qdrant(case_id)

    # 2. Database Delete
    db.delete(case)
    db.commit()

    logger.info(
        "Case and associated data deleted",
        extra={"case_id": case_id, "user_id": str(current_user.id)}
    )

    return CaseDeleteResponse(
        status="success",
        message="Case permanently deleted.",
    )


# ── AI Analysis Endpoints ─────────────────────────────────────────────────────

@router.post("/{case_id}/analyze", status_code=202, response_model=CaseAnalyzeResponse)
async def start_analysis(
    case_id: str,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    force: bool = False,
) -> CaseAnalyzeResponse:
    """
    Start the asynchronous AI analysis (LangGraph) for a case.

    Requirements: At least one document uploaded, all OCR processing completed.

    Args:
        case_id: UUID of the case.
        force: If True, restarts analysis even if already completed.
        background_tasks: FastAPI background worker.

    Returns:
        CaseAnalyzeResponse: Acceptance confirmation.

    Raises:
        HTTPException:
            422: No documents found.
            409: OCR incomplete or analysis already done (without force).
    """
    case = get_owned_case(case_id, current_user, db)
    docs = case.documents

    if not docs:
        raise HTTPException(status_code=422, detail="No documents in case.")

    # Status check: all documents must be processed
    in_progress = [d for d in docs if d.ocr_status not in ("completed", "error")]
    if in_progress:
        raise HTTPException(
            status_code=409,
            detail=f"{len(in_progress)} document(s) still processing. Please wait.",
        )

    # Status guard: avoid redundant analysis
    current_data = case.extracted_data or {}
    has_error = bool(current_data.get("error"))
    if not force and case.status != "DRAFT" and not has_error:
        raise HTTPException(
            status_code=409,
            detail=f"Analysis already completed (Status: {case.status}).",
        )

    # Clear previous results to trigger polling refresh in frontend
    case.extracted_data = {}
    db.commit()

    logger.info(
        "Analysis started",
        extra={"case_id": case_id, "force": force}
    )
    background_tasks.add_task(_run_analysis_background, case_id)

    return CaseAnalyzeResponse(
        status="accepted",
        message="AI analysis has been started.",
    )


@router.get("/{case_id}/analysis/result", response_model=AnalysisResultResponse)
def get_analysis_result(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> AnalysisResultResponse:
    """
    Retrieve current analysis results (for polling).

    Returns:
        AnalysisResultResponse: Status ('analyzing' | 'waiting_for_user' | 'error').

    Raises:
        HTTPException: If results are not yet available (404).
    """
    case = get_owned_case(case_id, current_user, db)
    data = case.extracted_data or {}

    # Check if analysis has produced ANY relevant output yet
    if not data or ("extracted_at" not in data and "missing_data" not in data and "error" not in data and "confirmed" not in data):
        raise HTTPException(status_code=404, detail="Analysis results not yet available.")

    if data.get("error"):
        return AnalysisResultResponse(
            status="error",
            error_message="Analysis failed. Please restart.",
        )

    return AnalysisResultResponse(
        status="waiting_for_user",
        extracted_data=data,
    )


@router.put("/{case_id}/analysis/confirm", status_code=202, response_model=ConfirmAnalysisResponse)
async def confirm_analysis(
    case_id: str,
    payload: ConfirmAnalysisRequest,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ConfirmAnalysisResponse:
    """
    Confirm extracted data (Human-in-the-Loop HiTL, US-3.5).

    Immediately sets status to BUILDING_TIMELINE and resumes the LangGraph agent.

    Args:
        case_id: UUID of the case.
        payload: Field corrections from the user.

    Returns:
        ConfirmAnalysisResponse: Redirection target.

    Raises:
        HTTPException: If case is not in WAITING_FOR_USER status (409).
    """
    case = get_owned_case(case_id, current_user, db)

    confirmed_update = {
        "meter_number": payload.meter_number,
        "malo_id": payload.malo_id,
        "dispute_amount": payload.dispute_amount,
        "network_operator": payload.network_operator,
        "opponent_category": payload.opponent_category,
        "opponent_name": payload.opponent_name,
    }

    # Handle subsequent updates if timeline is already ready
    if case.status in ["TIMELINE_READY", "BUILDING_TIMELINE"]:
        data = dict(case.extracted_data or {})
        data.update(confirmed_update)
        case.extracted_data = data
        db.commit()
        return ConfirmAnalysisResponse(status="confirmed", next_step="timeline")

    if case.status != "WAITING_FOR_USER":
        raise HTTPException(
            status_code=409,
            detail="Case is not in status WAITING_FOR_USER.",
        )

    # Race-Condition Guard: set status before starting background task
    case.status = "BUILDING_TIMELINE"
    db.commit()

    background_tasks.add_task(_resume_graph_background, case_id, confirmed_update)

    logger.info("Case confirmed, proceeding to timeline build", extra={"case_id": case_id})
    return ConfirmAnalysisResponse(status="confirmed", next_step="timeline")


# ── Status and Result Visualization Endpoints ─────────────────────────────────

@router.get("/{case_id}/status", response_model=CaseStatusResponse)
def get_case_status(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> CaseStatusResponse:
    """
    Get aggregated document processing status for a case.

    Used by the frontend to show upload progress.

    Returns:
        CaseStatusResponse: Aggregated document status ('processing' | 'completed' | 'error').
    """
    case = get_owned_case(case_id, current_user, db)
    docs = case.documents

    if not docs:
        return CaseStatusResponse(status="empty", total=0, completed=0)

    statuses = [d.ocr_status for d in docs]
    if any(s in ("processing", "parsing", "pending", "llama_parse_fallback") for s in statuses):
        agg_status = "processing"
    elif any(s == "error" for s in statuses):
        agg_status = "error"
    else:
        agg_status = "completed"

    completed_count = sum(1 for s in statuses if s == "completed")
    # Preview logic: return first few bytes of masked text from a finished doc
    preview_doc = next((d for d in docs if d.ocr_status == "completed" and d.masked_text), None)
    preview = preview_doc.masked_text[:500] if preview_doc else None

    return CaseStatusResponse(
        status=agg_status,
        total=len(docs),
        completed=completed_count,
        preview=preview,
    )


@router.get("/{case_id}/extraction-result", response_model=ExtractionResultResponse)
def get_extraction_result(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> ExtractionResultResponse:
    """
    Get detailed extraction results with confidence metadata (US-9.2).

    Supports split-view highlighting for fields requiring manual review.

    Returns:
        ExtractionResultResponse: Detailed field scores.
    """
    case = get_owned_case(case_id, current_user, db)
    data = case.extracted_data or {}

    if not data or ("extracted_at" not in data and "confirmed" not in data):
        raise HTTPException(status_code=404, detail="Analysis results not yet available.")

    field_confidences: dict = data.get("field_confidences", {})
    source_snippets: dict = data.get("source_snippets", {})
    source_doc_ids: dict = data.get("source_doc_ids", {})

    def _make_field(key: str, value: object) -> ExtractionFieldResponse:
        confidence = field_confidences.get(key, 0.6 if value is not None else 0.0)
        return ExtractionFieldResponse(
            key=key,
            value=value,
            confidence=confidence,
            needs_review=confidence < CONFIDENCE_THRESHOLD,
            auto_accepted=confidence >= CONFIDENCE_THRESHOLD and value is not None,
            source_document_id=source_doc_ids.get(key),
            source_text_snippet=source_snippets.get(key),
        )

    fields = [
        _make_field("malo_id", data.get("malo_id")),
        _make_field("meter_number", data.get("meter_number")),
        _make_field("dispute_amount", data.get("dispute_amount")),
        _make_field("network_operator", data.get("network_operator")),
    ]

    # Opponent Metadata
    opponent_confidence = data.get("opponent_confidence", 0.0)
    opponent = OpponentResponse(
        category=data.get("opponent_category") or case.opponent_category,
        name=data.get("opponent_name") or case.opponent_name,
        confidence=opponent_confidence,
        needs_review=opponent_confidence < CONFIDENCE_THRESHOLD,
    )

    return ExtractionResultResponse(fields=fields, opponent=opponent)


@router.patch("/{case_id}", response_model=UpdateOpponentResponse)
def update_case_opponent(
    case_id: str,
    payload: UpdateOpponentRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> UpdateOpponentResponse:
    """
    Manually update the case's opponent classification (US-9.4).

    Synchronizes the primary case table and the extracted_data JSON blob.
    """
    case = get_owned_case(case_id, current_user, db)
    data = dict(case.extracted_data or {})

    if payload.opponent_category is not None:
        case.opponent_category = payload.opponent_category
        data["opponent_category"] = payload.opponent_category

    if payload.opponent_name is not None:
        case.opponent_name = payload.opponent_name
        data["opponent_name"] = payload.opponent_name

    case.extracted_data = data
    db.commit()

    logger.info(
        "Opponent details updated",
        extra={
            "case_id": case_id,
            "category": payload.opponent_category,
            "name": payload.opponent_name
        }
    )
    return UpdateOpponentResponse(status="updated")


# ── Background Worker Tasks (LangGraph Orchestration) ────────────────────────

async def _run_analysis_background(case_id: str) -> None:
    """Run the analysis agent graph for a case thread."""
    from app.agents.graph import get_agent_app

    logger.info("Internal: analysis background task started", extra={"case_id": case_id})
    config = {"configurable": {"thread_id": case_id}}
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
        "opponent_category": None,
        "opponent_name": None,
        "opponent_confidence": 0.0,
        "field_confidences": {},
        "source_snippets": {},
        "source_doc_ids": {},
        "chronology": [],
        "missing_info": [],
        "dossier_ready": False,
        "payment_status": "pending",
        # Epic 4
        "events_per_doc": {},
        "new_document_id": None,
    }

    try:
        agent_app = await get_agent_app()
        # Ensure fresh thread state
        await _clear_checkpoint(case_id)
        # Start LangGraph
        await agent_app.ainvoke(initial_state, config=config)
    except Exception as exc:
        logger.error(
            "AI Agent core loop failed",
            extra={"case_id": case_id, "error": str(exc)},
            exc_info=True
        )
        _set_case_error(case_id)


async def _resume_graph_background(case_id: str, confirmed_update: dict) -> None:
    """Resume the LangGraph agent after HiTL confirmation."""
    from app.agents.graph import get_agent_app

    config = {"configurable": {"thread_id": case_id}}
    try:
        agent_app = await get_agent_app()
        # 1. Update graph state with HiTL corrections
        await agent_app.aupdate_state(config, confirmed_update)
        # 2. Resume execution (passing None to trigger the next node)
        await agent_app.ainvoke(None, config=config)
        logger.info("Graph resume completed", extra={"case_id": case_id})
    except Exception as exc:
        logger.error(
            "Graph resume failed",
            extra={"case_id": case_id, "error": str(exc)},
            exc_info=True
        )
        _set_case_error(case_id)


async def _clear_checkpoint(case_id: str) -> None:
    """Clean up potentially corrupted LangGraph checkpoints in DB."""
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.postgres_checkpoint_url:
        return

    try:
        import psycopg
        async with await psycopg.AsyncConnection.connect(
            settings.postgres_checkpoint_url, autocommit=True
        ) as conn:
            await conn.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (case_id,))
            await conn.execute("DELETE FROM checkpoints WHERE thread_id = %s", (case_id,))
    except Exception as exc:
        logger.warning("Checkpoint cleanup failed", extra={"case_id": case_id, "error": str(exc)})


def _set_case_error(case_id: str) -> None:
    """Atomic update for analysis error state."""
    from app.infrastructure.database import get_db_context
    try:
        case_uuid = uuid.UUID(case_id)
        with get_db_context() as db:
            case = db.query(Case).filter(Case.id == case_uuid).first()
            if case:
                case.extracted_data = {"error": True}
                case.status = "ERROR"
                db.commit()
    except (ValueError, Exception):
        pass


# ── Cleanup Helpers ───────────────────────────────────────────────────────────

def _delete_from_storage(case: Case) -> None:
    """Delete all document files from S3/MinIO."""
    storage = get_storage()
    for document in case.documents:
        try:
            storage.delete_file(document.s3_key)
        except Exception as exc:
            logger.error(
                "Failed to delete S3 file during case cleanup",
                extra={"key": document.s3_key, "error": str(exc)}
            )


def _delete_from_qdrant(case_id: str) -> None:
    """Remove all vector embeddings for the case (GDPR Hard-Delete)."""
    from app.core.config import get_settings
    from app.infrastructure.qdrant_client import delete_by_case

    try:
        settings = get_settings()
        delete_by_case(
            collection=settings.qdrant_collection,
            case_id=case_id,
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
    except Exception as exc:
        logger.error(
            "Failed to delete Qdrant vectors during case cleanup",
            extra={"case_id": case_id, "error": str(exc)}
        )
