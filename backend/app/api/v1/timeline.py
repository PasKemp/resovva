"""
Timeline Router – Epic 4: Der Rote Faden.

Endpunkte:
  GET    /cases/{case_id}/timeline              – Timeline laden (US-4.3 Polling)
  POST   /cases/{case_id}/timeline/refresh      – Inkrementelles Update (US-4.5)
  POST   /cases/{case_id}/timeline              – Manuelles Ereignis hinzufügen (US-4.4)
  PATCH  /cases/{case_id}/timeline/{event_id}   – Ereignis bearbeiten (US-4.3)
  DELETE /cases/{case_id}/timeline/{event_id}   – Ereignis/Lücke löschen (US-4.3)

Mandantenfähigkeit: get_owned_case(case_id, current_user, db) → 404 wenn fremd.
Schutzregel: source_type='user' Events werden NIEMALS durch KI überschrieben.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, get_owned_case
from app.domain.models.db import Case, ChronologyEvent, Document
from app.infrastructure.database import get_db

router = APIRouter(tags=["timeline"])
logger = logging.getLogger(__name__)


# ── Pydantic Schemas ───────────────────────────────────────────────────────────


class TimelineEventResponse(BaseModel):
    event_id:      str
    case_id:       str
    event_date:    Optional[str]  # "YYYY-MM-DD" oder null
    description:   str
    source_doc_id: Optional[str]
    source_type:   str            # 'ai' | 'user'
    is_gap:        bool


class TimelineResponse(BaseModel):
    status: str                           # 'building' | 'ready' | 'empty'
    events: List[TimelineEventResponse]


class AddEventRequest(BaseModel):
    event_date:  date
    description: str = Field(..., min_length=1, max_length=500)

    @field_validator("event_date")
    @classmethod
    def date_not_in_future(cls, v: date) -> date:
        from datetime import date as _date
        if v > _date.today():
            raise ValueError("Datum darf nicht in der Zukunft liegen.")
        return v


class UpdateEventRequest(BaseModel):
    event_date:  Optional[date] = None
    description: Optional[str] = Field(None, max_length=500)

    @field_validator("event_date")
    @classmethod
    def date_not_in_future(cls, v: Optional[date]) -> Optional[date]:
        if v is None:
            return v
        from datetime import date as _date
        if v > _date.today():
            raise ValueError("Datum darf nicht in der Zukunft liegen.")
        return v


class TimelineRefreshResponse(BaseModel):
    status:  str
    message: str


# ── Helper ─────────────────────────────────────────────────────────────────────


def _event_to_response(e: ChronologyEvent) -> TimelineEventResponse:
    return TimelineEventResponse(
        event_id=str(e.id),
        case_id=str(e.case_id),
        event_date=e.event_date.isoformat() if e.event_date else None,
        description=e.description,
        source_doc_id=str(e.source_doc_id) if e.source_doc_id else None,
        source_type=e.source_type,
        is_gap=e.is_gap,
    )


def _get_event_or_404(db: Session, event_id: str, case_id: uuid.UUID) -> ChronologyEvent:
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Ereignis nicht gefunden.")
    event = db.query(ChronologyEvent).filter(
        ChronologyEvent.id == event_uuid,
        ChronologyEvent.case_id == case_id,
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Ereignis nicht gefunden.")
    return event


# ── GET /cases/{case_id}/timeline ─────────────────────────────────────────────


@router.get("/cases/{case_id}/timeline", response_model=TimelineResponse)
async def get_timeline(
    case_id:      str,
    current_user: CurrentUser,
    db:           Session = Depends(get_db),
) -> TimelineResponse:
    """
    Lädt die Timeline des Falls.

    Polling-Semantik:
    - status='building' wenn KI noch rechnet (BUILDING_TIMELINE)
    - status='ready'    wenn Timeline fertig (Events vorhanden)
    - status='empty'    wenn noch keine Events existieren
    """
    case = get_owned_case(case_id, current_user, db)

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


# ── POST /cases/{case_id}/timeline/refresh ────────────────────────────────────
# Muss VOR /{event_id} registriert sein (FastAPI: literal > parametrized)


@router.post("/cases/{case_id}/timeline/refresh", response_model=TimelineRefreshResponse, status_code=202)
async def refresh_timeline(
    case_id:          str,
    background_tasks: BackgroundTasks,
    current_user:     CurrentUser,
    document_id:      str = Query(..., description="UUID des neu hochgeladenen Dokuments"),
    db:               Session = Depends(get_db),
) -> TimelineRefreshResponse:
    """
    Startet inkrementelles Timeline-Update für ein einzelnes neues Dokument (US-4.5).

    Das Dokument muss bereits OCR-abgeschlossen sein.
    """
    from app.agents.nodes.incremental_update import run_incremental_update

    case = get_owned_case(case_id, current_user, db)

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Ungültige Dokument-ID.")

    doc = db.query(Document).filter(
        Document.id == doc_uuid,
        Document.case_id == case.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    if doc.ocr_status != "completed":
        raise HTTPException(status_code=422, detail="Dokument noch nicht vollständig verarbeitet.")

    case.status = "BUILDING_TIMELINE"
    db.commit()

    background_tasks.add_task(run_incremental_update, str(case.id), document_id)

    return TimelineRefreshResponse(
        status="accepted",
        message="Inkrementelles Timeline-Update gestartet.",
    )


# ── POST /cases/{case_id}/timeline ────────────────────────────────────────────


@router.post("/cases/{case_id}/timeline", response_model=TimelineEventResponse, status_code=201)
async def add_timeline_event(
    case_id:      str,
    payload:      AddEventRequest,
    current_user: CurrentUser,
    db:           Session = Depends(get_db),
) -> TimelineEventResponse:
    """Fügt ein manuelles Ereignis hinzu (US-4.4). Wird als source_type='user' markiert."""
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
    logger.info("Timeline: Manuelles Ereignis %s für Case %s hinzugefügt.", event.id, case.id)
    return _event_to_response(event)


# ── PATCH /cases/{case_id}/timeline/{event_id} ────────────────────────────────


@router.patch("/cases/{case_id}/timeline/{event_id}", response_model=TimelineEventResponse)
async def update_timeline_event(
    case_id:      str,
    event_id:     str,
    payload:      UpdateEventRequest,
    current_user: CurrentUser,
    db:           Session = Depends(get_db),
) -> TimelineEventResponse:
    """Bearbeitet ein Ereignis (US-4.3). Sowohl AI- als auch User-Events editierbar."""
    case = get_owned_case(case_id, current_user, db)
    event = _get_event_or_404(db, event_id, case.id)

    if payload.event_date is not None:
        event.event_date = payload.event_date
    if payload.description is not None:
        event.description = payload.description

    db.commit()
    db.refresh(event)
    return _event_to_response(event)


# ── DELETE /cases/{case_id}/timeline/{event_id} ───────────────────────────────


@router.delete("/cases/{case_id}/timeline/{event_id}", status_code=204)
async def delete_timeline_event(
    case_id:      str,
    event_id:     str,
    current_user: CurrentUser,
    db:           Session = Depends(get_db),
) -> None:
    """
    Löscht ein Ereignis (US-4.3).

    - AI-Events: direkt löschbar
    - User-Events: ebenfalls löschbar
    - Gap-Events (is_gap=True): Löschen = 'Ignorieren'
    """
    case = get_owned_case(case_id, current_user, db)
    event = _get_event_or_404(db, event_id, case.id)
    db.delete(event)
    db.commit()
    logger.info("Timeline: Ereignis %s gelöscht (Case %s).", event_id, case.id)
