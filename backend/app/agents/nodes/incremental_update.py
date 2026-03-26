"""
run_incremental_update – Inkrementelles Timeline-Update (US-4.5).

Standalone-Async-Funktion (NICHT im LangGraph-Graph).
Wird direkt vom /timeline/refresh-Endpoint als BackgroundTask aufgerufen.

Verarbeitet NUR das neu hochgeladene Dokument (nicht alle Docs).
Merged neue Events in die bestehende Timeline.
User-Events (source_type='user') bleiben IMMER unberührt.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import date
from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.agents.nodes.build_master_timeline import MasterTimeline, _get_llm
from app.agents.nodes.extract import _get_mini_llm
from app.infrastructure.database import get_db_context

logger = logging.getLogger(__name__)


# ── Pydantic für einzelnes Dokument ───────────────────────────────────────────


class SingleDocEvent(BaseModel):
    event_date: Optional[date] = Field(None, description="ISO-Datum oder null.")
    description: str = Field(..., description="Kurze Beschreibung (max. 200 Zeichen).")


class SingleDocEvents(BaseModel):
    events: List[SingleDocEvent] = Field(default_factory=list)


_SINGLE_DOC_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Du bist ein präziser Assistent für deutsche Rechtsstreit-Chronologien. "
        "Extrahiere alle zeitlich relevanten Ereignisse aus diesem neuen Dokument.\n\n"
        "Regeln:\n"
        "1. Extrahiere das Erstellungsdatum des Dokuments.\n"
        "2. Extrahiere alle referenzierten Ereignisse ('am 12.04. besprochen').\n"
        "3. Beschreibung: prägnanter deutscher Satz.\n"
        "4. null wenn kein Datum bestimmbar.\n\n"
        "Dokumentname: {filename}\nText:\n{text}",
    ),
    ("human", "Extrahiere alle Ereignisse aus diesem neuen Dokument."),
])

_MERGE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Du bist ein juristischer Assistent für deutsche Rechtsstreit-Chronologien.\n\n"
        "Die folgende Chronologie ist BEREITS BESTÄTIGT. "
        "Füge NUR neue, eindeutig nicht bereits vorhandene Ereignisse aus den 'Neue Ereignisse' hinzu.\n\n"
        "Regeln:\n"
        "1. Dedupliziere: Event NICHT hinzufügen wenn gleicher Inhalt oder gleiches Datum+Typ bereits existiert.\n"
        "2. Sortiere chronologisch (ältester Eintrag zuerst). Einträge ohne Datum ans Ende.\n"
        "3. Gap-Analyse für die GESAMTE Timeline (bestehende + neue Events):\n"
        "   - Mahnung ohne Rechnung → Gap 'Rechnung'\n"
        "   - Inkasso ohne Mahnung → Gap 'Mahnung'\n"
        "   - Neuer Vertrag ohne Kündigung → Gap 'Kündigung'\n"
        "4. Maximal 5 Gap-Einträge gesamt.\n"
        "5. Events mit Markierung '[USER]' sind UNVERÄNDERLICH – niemals entfernen oder zusammenführen.\n\n"
        "Bestehende Timeline:\n{existing_events}\n\n"
        "Neue Ereignisse:\n{new_events}",
    ),
    ("human", "Erstelle die aktualisierte Master-Chronologie."),
])


async def run_incremental_update(case_id: str, document_id: str) -> None:
    """
    Verarbeitet ein einzelnes neues Dokument und merged Events in die bestehende Timeline.

    Aufgerufen als BackgroundTask von POST /cases/{case_id}/timeline/refresh.
    """
    from app.domain.models.db import Case, ChronologyEvent, Document

    try:
        case_uuid = _uuid.UUID(case_id)
        doc_uuid = _uuid.UUID(document_id)
    except ValueError:
        logger.error("incremental_update: Ungültige UUIDs case=%s doc=%s", case_id, document_id)
        return

    # Status → BUILDING_TIMELINE
    with get_db_context() as db:
        case = db.query(Case).filter(Case.id == case_uuid).first()
        if not case:
            logger.error("incremental_update: Case %s nicht gefunden.", case_uuid)
            return
        case.status = "BUILDING_TIMELINE"
        db.commit()

    # Dokument laden
    with get_db_context() as db:
        doc = db.query(Document).filter(
            Document.id == doc_uuid,
            Document.case_id == case_uuid,
        ).first()
        if not doc or not doc.masked_text:
            logger.error("incremental_update: Dokument %s nicht gefunden oder kein Text.", doc_uuid)
            _set_status(case_uuid, "TIMELINE_READY")
            return
        doc_filename = doc.filename
        doc_text = doc.masked_text

    # Schritt 1: Events aus neuem Dokument extrahieren
    logger.info("incremental_update: Extrahiere Events aus Dok %s.", doc_uuid)
    try:
        mini_llm = _get_mini_llm()
        chain = _SINGLE_DOC_PROMPT | mini_llm.with_structured_output(SingleDocEvents)
        new_doc_result: SingleDocEvents = await chain.ainvoke({
            "filename": doc_filename,
            "text":     doc_text[:6000],
        })
        new_events = new_doc_result.events
    except Exception as exc:
        logger.error("incremental_update: LLM-Fehler bei Extraktion: %s", exc)
        _set_status(case_uuid, "TIMELINE_READY")
        return

    if not new_events:
        logger.info("incremental_update: Keine neuen Events gefunden – keine Änderung.")
        _set_status(case_uuid, "TIMELINE_READY")
        return

    # Schritt 2: Bestehende Timeline laden
    with get_db_context() as db:
        existing = db.query(ChronologyEvent).filter(
            ChronologyEvent.case_id == case_uuid,
        ).order_by(ChronologyEvent.event_date.asc().nullslast()).all()
        existing_data = [
            {
                "id":          str(e.id),
                "event_date":  e.event_date.isoformat() if e.event_date else None,
                "description": e.description,
                "source_type": e.source_type,
                "is_gap":      e.is_gap,
                "source_doc_id": str(e.source_doc_id) if e.source_doc_id else None,
            }
            for e in existing
        ]

    # Schritt 3: Merge via gpt-4o
    existing_lines = []
    for e in existing_data:
        prefix = "[USER] " if e["source_type"] == "user" else ""
        date_str = e["event_date"] or "Datum unbekannt"
        existing_lines.append(f"- {prefix}[{date_str}] {e['description']}")

    new_lines = []
    for e in new_events:
        date_str = e.event_date.isoformat() if e.event_date else "Datum unbekannt"
        new_lines.append(f"- [{date_str}] {e.description} (Dok: {document_id})")

    logger.info("incremental_update: Merge %d bestehende + %d neue Events via gpt-4o.", len(existing_data), len(new_events))
    try:
        llm = _get_llm()
        chain = _MERGE_PROMPT | llm.with_structured_output(MasterTimeline)
        merged: MasterTimeline = await chain.ainvoke({
            "existing_events": "\n".join(existing_lines),
            "new_events":      "\n".join(new_lines),
        })
    except Exception as exc:
        logger.error("incremental_update: Merge-LLM-Fehler: %s", exc)
        _set_status(case_uuid, "TIMELINE_READY")
        return

    # Schritt 4: Persistieren (DELETE nur AI-Events, dann INSERT)
    with get_db_context() as db:
        db.query(ChronologyEvent).filter(
            ChronologyEvent.case_id == case_uuid,
            ChronologyEvent.source_type == "ai",
        ).delete(synchronize_session=False)

        for e in merged.events:
            source_doc_id = None
            if e.source_doc_id:
                try:
                    source_doc_id = _uuid.UUID(e.source_doc_id)
                except ValueError:
                    pass

            db.add(ChronologyEvent(
                id=_uuid.uuid4(),
                case_id=case_uuid,
                event_date=e.event_date,
                description=e.description[:500],
                source_doc_id=source_doc_id,
                source_type="ai",
                is_gap=e.is_gap,
            ))

        case = db.query(Case).filter(Case.id == case_uuid).first()
        if case:
            case.status = "TIMELINE_READY"
        db.commit()

    gaps = sum(1 for e in merged.events if e.is_gap)
    logger.info(
        "incremental_update: %d Events (%d Lücken) nach Merge für Case %s.",
        len(merged.events), gaps, case_uuid,
    )


def _set_status(case_uuid: _uuid.UUID, status: str) -> None:
    """Setzt case.status ohne weitere Änderungen."""
    from app.domain.models.db import Case

    with get_db_context() as db:
        case = db.query(Case).filter(Case.id == case_uuid).first()
        if case:
            case.status = status
            db.commit()
