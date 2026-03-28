"""
Timeline Router.

Manages the case chronology including AI-generated events, manual user events,
and identified evidential gaps. Supports incremental updates when new
documents are uploaded.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import (
    APIRouter, BackgroundTasks, Depends, HTTPException, Query
)
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, get_owned_case
from app.api.v1.schemas.timeline import (
    AddEventRequest,
    TimelineEventResponse,
    TimelineRefreshResponse,
    TimelineResponse,
    UpdateEventRequest,
)
from app.domain.models.db import ChronologyEvent, Document
from app.infrastructure.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["timeline"])


# ── Internal Helpers ──────────────────────────────────────────────────────────

def _event_to_response(event: ChronologyEvent) -> TimelineEventResponse:
    """Map a SQLAlchemy event model to a Pydantic response schema."""
    return TimelineEventResponse(
        event_id=str(event.id),
        case_id=str(event.case_id),
        event_date=event.event_date.isoformat() if event.event_date else None,
        description=event.description,
        source_doc_id=str(event.source_doc_id) if event.source_doc_id else None,
        source_type=event.source_type,
        is_gap=event.is_gap,
    )


def _get_event_or_404(db: Session, event_id: str, case_id: uuid.UUID) -> ChronologyEvent:
    """Retrieve an event by ID or raise 404."""
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Timeline event not found.")

    event = db.query(ChronologyEvent).filter(
        ChronologyEvent.id == event_uuid,
        ChronologyEvent.case_id == case_id
    ).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Timeline event not found.")
    return event


# ── Timeline Endpoints ───────────────────────────────────────────────────────

@router.get("/{case_id}/timeline", response_model=TimelineResponse)
async def get_timeline(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> TimelineResponse:
    """
    Retrieve the chronology of a case.

    Polling semantics:
    - 'building': The AI agent is still processing the timeline.
    - 'ready': Events exist and are ready for display.
    - 'empty': No events have been generated or added yet.

    Returns:
        TimelineResponse: Status and list of events.
    """
    case = get_owned_case(case_id, current_user, db)

    # Status check for AI agent processing
    if case.status == "ERROR" or (case.extracted_data or {}).get("error"):
        return TimelineResponse(status="error", events=[])

    if case.status == "BUILDING_TIMELINE":
        return TimelineResponse(status="building", events=[])

    events = (
        db.query(ChronologyEvent)
        .filter(ChronologyEvent.case_id == case.id)
        .order_by(ChronologyEvent.event_date.asc().nullslast())
        .all()
    )

    if not events:
        return TimelineResponse(status="empty", events=[])

    return TimelineResponse(
        status="ready",
        events=[_event_to_response(e) for e in events],
    )


@router.post("/{case_id}/timeline/refresh", status_code=202, response_model=TimelineRefreshResponse)
async def refresh_timeline(
    case_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    document_id: str = Query(..., description="UUID of the newly uploaded document"),
    db: Session = Depends(get_db),
) -> TimelineRefreshResponse:
    """
    Trigger an incremental timeline update for a single new document (US-4.5).

    The document must have 'completed' OCR status.

    Args:
        case_id: UUID of the case.
        document_id: UUID of the new evidence document.

    Returns:
        TimelineRefreshResponse: Acceptance message.
    """
    from app.agents.nodes.incremental_update import run_incremental_update

    case = get_owned_case(case_id, current_user, db)

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid document ID format.")

    doc = db.query(Document).filter(
        Document.id == doc_uuid,
        Document.case_id == case.id
    ).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    if doc.ocr_status != "completed":
        raise HTTPException(status_code=422, detail="Document processing incomplete.")

    # Mark case for polling
    case.status = "BUILDING_TIMELINE"
    db.commit()

    background_tasks.add_task(run_incremental_update, str(case.id), document_id)

    logger.info(
        "Incremental timeline refresh started",
        extra={"case_id": case_id, "document_id": document_id}
    )

    return TimelineRefreshResponse(
        status="accepted",
        message="Incremental timeline update started."
    )


@router.post("/{case_id}/timeline", status_code=201, response_model=TimelineEventResponse)
async def add_timeline_event(
    case_id: str,
    payload: AddEventRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> TimelineEventResponse:
    """
    Manually add an event to the chronology (US-4.4).

    Events created via this endpoint are marked as source_type='user' and
    are never overwritten by AI agents.
    """
    case = get_owned_case(case_id, current_user, db)

    event = ChronologyEvent(
        id=uuid.uuid4(),
        case_id=case.id,
        event_date=payload.event_date,
        description=payload.description,
        source_doc_id=None,
        source_type="user",
        is_gap=False,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    logger.info(
        "Manual timeline event added",
        extra={"case_id": case_id, "event_id": str(event.id)}
    )
    return _event_to_response(event)


@router.patch("/{case_id}/timeline/{event_id}", response_model=TimelineEventResponse)
async def update_timeline_event(
    case_id: str,
    event_id: str,
    payload: UpdateEventRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> TimelineEventResponse:
    """
    Update an existing chronology event.

    Applicable to both AI-generated and user-provided events.
    """
    case = get_owned_case(case_id, current_user, db)
    event = _get_event_or_404(db, event_id, case.id)

    if payload.event_date is not None:
        event.event_date = payload.event_date
    if payload.description is not None:
        event.description = payload.description

    db.commit()
    db.refresh(event)

    return _event_to_response(event)


@router.delete("/{case_id}/timeline/{event_id}", status_code=204)
async def delete_timeline_event(
    case_id: str,
    event_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> None:
    """
    Delete a chronology event (US-4.3).

    Gaps marked as is_gap=True can also be deleted to signifies 'ignoring' the gap.
    """
    case = get_owned_case(case_id, current_user, db)
    event = _get_event_or_404(db, event_id, case.id)

    db.delete(event)
    db.commit()

    logger.info(
        "Timeline event deleted",
        extra={"case_id": case_id, "event_id": event_id}
    )
