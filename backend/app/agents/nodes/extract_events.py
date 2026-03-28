"""
node_extract_events – Map-Phase: Ereignis-Extraktion pro Dokument (US-4.1).

Verarbeitet alle OCR-abgeschlossenen Dokumente parallel via asyncio.gather().
Nutzt gpt-4o-mini (kein teureres Modell ohne Ticket).

Output: state["events_per_doc"] = { doc_id: [ChronologyEvent, ...] }
Setzt case.status = "BUILDING_TIMELINE".
"""

from __future__ import annotations

import asyncio
import logging
import uuid as _uuid
from datetime import date
from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.agents.nodes.extract import _get_mini_llm
from app.agents.state import AgentState
from app.infrastructure.database import get_db_context

logger = logging.getLogger(__name__)


# ── Pydantic-Modelle für strukturierte LLM-Ausgabe ────────────────────────────


class ChronologyEventExtracted(BaseModel):
    event_date: Optional[date] = Field(
        None,
        description=(
            "Datum des Ereignisses als ISO-Datum (YYYY-MM-DD). "
            "Auch referenzierte Daten extrahieren ('am 12.04. besprochen', 'Kündigung vom 01.03.'). "
            "Bei unklarem Jahr das wahrscheinlichste aus dem Dokumentkontext verwenden. "
            "null wenn kein Datum bestimmbar."
        ),
    )
    description: str = Field(
        ...,
        description="Prägnanter deutscher Satz, der das Ereignis beschreibt (max. 200 Zeichen).",
    )


class DocumentEvents(BaseModel):
    events: List[ChronologyEventExtracted] = Field(
        default_factory=list,
        description="Alle extrahierten Ereignisse aus diesem Dokument, chronologisch.",
    )


# ── Prompt ─────────────────────────────────────────────────────────────────────

_EVENTS_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Du bist ein präziser Assistent für deutsche Rechtsstreit-Chronologien. "
        "Extrahiere ALLE zeitlich relevanten Ereignisse aus diesem Dokument.\n\n"
        "Regeln:\n"
        "1. Extrahiere das Erstellungsdatum des Dokuments selbst (z.B. Rechnungsdatum, Briefdatum).\n"
        "2. Extrahiere referenzierte Ereignisse in der Vergangenheit "
        "('wurde am 12.04. besprochen', 'Kündigung vom 01.03.', 'Mahnung vom 15.02.').\n"
        "3. Beschreibe jeden Eintrag in einem prägnanten deutschen Satz.\n"
        "4. Bei unklarem Jahr: verwende das wahrscheinlichste Jahr aus dem Dokumentkontext.\n"
        "5. null wenn kein Datum bestimmbar.\n\n"
        "Dokumenttyp: {doc_type}\nDokumentname: {filename}\n\nText:\n{text}",
    ),
    ("human", "Extrahiere alle Ereignisse aus diesem Dokument."),
])


# ── Hilfsfunktion: ein Dokument verarbeiten ────────────────────────────────────


async def _extract_for_doc(doc_id: str, filename: str, doc_type: str, text: str) -> tuple[str, list]:
    """Extrahiert Events aus einem einzelnen Dokument. Gibt (doc_id, events_list) zurück."""
    llm = _get_mini_llm()
    chain = _EVENTS_PROMPT | llm.with_structured_output(DocumentEvents)
    result: DocumentEvents = await chain.ainvoke({
        "doc_type": doc_type,
        "filename": filename,
        "text":     text[:6000],  # Kosten begrenzen
    })
    events = []
    for e in result.events:
        events.append({
            "date":          e.event_date.isoformat() if e.event_date else None,
            "description":   e.description[:200],
            "source_doc_id": doc_id,
            "source_type":   "ai",
            "is_gap":        False,
        })
    return doc_id, events


# ── Node ───────────────────────────────────────────────────────────────────────


async def node_extract_events(state: AgentState) -> AgentState:
    """
    Map-Phase: Extrahiert Ereignisse aus jedem Dokument parallel (US-4.1).

    Setzt case.status = 'BUILDING_TIMELINE' und
    state['events_per_doc'] = { doc_id: [ChronologyEvent, ...] }.
    """
    from app.domain.models.db import Case, Document

    case_id = state["case_id"]
    messages = state.get("messages") or []

    try:
        case_uuid = _uuid.UUID(case_id)
    except (ValueError, KeyError):
        logger.error("extract_events: Ungültige Case-ID %s.", case_id)
        return {**state, "current_step": "extract_events_error", "events_per_doc": {}}

    try:
        # Status → BUILDING_TIMELINE
        with get_db_context() as db:
            case = db.query(Case).filter(Case.id == case_uuid).first()
            if case:
                case.status = "BUILDING_TIMELINE"
                db.commit()

            docs = (
                db.query(Document)
                .filter(
                    Document.case_id == case_uuid,
                    Document.ocr_status == "completed",
                    Document.masked_text.isnot(None),
                )
                .all()
            )
            doc_data = [
                (str(d.id), d.filename, d.document_type or "UNKNOWN", d.masked_text)
                for d in docs
            ]

        if not doc_data:
            logger.warning("extract_events: Keine abgeschlossenen Dokumente für Case %s.", case_uuid)
            return {
                **state,
                "current_step": "extract_events",
                "events_per_doc": {},
                "messages": messages + ["System: Keine Dokumente für Ereignis-Extraktion."],
            }

        logger.info("extract_events: %d Dokumente werden parallel verarbeitet.", len(doc_data))

        tasks = [_extract_for_doc(doc_id, fname, dtype, text) for doc_id, fname, dtype, text in doc_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        events_per_doc: dict = {}
        for res in results:
            if isinstance(res, Exception):
                logger.warning("extract_events: Fehler bei Dokument-Verarbeitung: %s", res)
                continue
            doc_id, events = res
            events_per_doc[doc_id] = events
            logger.debug("extract_events: %d Events aus Dok %s extrahiert.", len(events), doc_id)

        total = sum(len(v) for v in events_per_doc.values())
        logger.info("extract_events: %d Events aus %d Dokumenten extrahiert.", total, len(events_per_doc))

        return {
            **state,
            "current_step": "extract_events",
            "events_per_doc": events_per_doc,
            "messages": messages + [f"System: {total} Ereignisse aus {len(events_per_doc)} Dokumenten extrahiert."],
        }
    except Exception as exc:
        logger.error("extract_events: Globaler Fehler in Node: %s", exc, exc_info=True)
        return {
            **state,
            "current_step": "extract_events_error",
            "events_per_doc": {},
            "messages": messages + [f"System: Fehler bei Ereignis-Extraktion: {exc}"],
        }
