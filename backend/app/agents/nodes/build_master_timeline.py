"""
node_build_master_timeline – Reduce-Phase: Deduplizierung, Sortierung & Gap-Analyse (US-4.2).

Nutzt gpt-4o (nicht mini – höhere Reasoning-Qualität für Deduplizierung nötig).
Schreibt ChronologyEvent-Zeilen in DB.
Setzt case.status = 'TIMELINE_READY'.

Schutzregel: Ereignisse mit source_type='user' werden NIEMALS verändert oder gelöscht.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import date
from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.agents.state import AgentState
from app.infrastructure.database import get_db_context

logger = logging.getLogger(__name__)


# ── LLM Factory (gpt-4o – nicht Mini) ─────────────────────────────────────────


def _get_llm():
    """Liefert strikt gpt-4o für Reasoning-intensive Reduce-Phase."""
    from app.core.config import get_settings

    settings = get_settings()
    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint.rstrip("/"),
            api_key=settings.azure_openai_api_key,
            azure_deployment=settings.azure_openai_deployment or "gpt-4o",
            openai_api_version=settings.openai_api_version,
            temperature=0,
            timeout=90,
        )

    from langchain_openai import ChatOpenAI

    kwargs = {}
    if settings.openai_api_key:
        kwargs["api_key"] = settings.openai_api_key

    return ChatOpenAI(model="gpt-4o", temperature=0, timeout=90, **kwargs)


# ── Pydantic-Modelle ───────────────────────────────────────────────────────────


class MasterEvent(BaseModel):
    event_date: Optional[date] = Field(
        None,
        description="ISO-Datum (YYYY-MM-DD) oder null wenn nicht bestimmbar.",
    )
    description: str = Field(
        ...,
        description="Prägnanter deutscher Satz zum Ereignis (max. 200 Zeichen).",
    )
    source_doc_id: Optional[str] = Field(
        None,
        description="Dokument-UUID aus dem das Ereignis stammt (aus den Eingabe-Events).",
    )
    is_gap: bool = Field(
        False,
        description=(
            "true NUR für erkannte Lücken (fehlendes Dokument). "
            "Beschreibung dann: 'Vermutlich fehlendes Dokument: Rechnung vom 01.03.'"
        ),
    )


class MasterTimeline(BaseModel):
    events: List[MasterEvent] = Field(
        default_factory=list,
        description="Vollständige, deduplizierte, chronologisch sortierte Timeline inkl. Lücken.",
    )


# ── Prompt ─────────────────────────────────────────────────────────────────────

_REDUCE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Du bist ein juristischer Assistent für deutsche Rechtsstreit-Chronologien.\n\n"
        "Aufgabe:\n"
        "1. Dedupliziere die folgenden Ereignisse (gleiche Ereignisse aus mehreren Dokumenten → ein Eintrag).\n"
        "2. Sortiere chronologisch, ältester Eintrag zuerst. Einträge ohne Datum ans Ende.\n"
        "3. Gap-Analyse: Erkenne logische Lücken und füge sie als is_gap=true ein:\n"
        "   - Mahnung referenziert Rechnung, die NICHT in der Timeline ist → Gap 'Rechnung' vor der Mahnung\n"
        "   - Inkasso-Schreiben ohne vorherige Mahnung → Gap 'Mahnung' vor dem Inkasso\n"
        "   - Neuer Vertrag ohne Kündigung des alten → Gap 'Kündigung' vor dem neuen Vertrag\n"
        "4. Maximal 5 Gap-Einträge einfügen.\n"
        "5. Beschreibe Gaps als: 'Vermutlich fehlendes Dokument: <Typ> vom <Datum>'\n\n"
        "WICHTIG: Erstelle eine saubere, vollständige Timeline ohne Duplikate.\n\n"
        "Ereignisse aus den Dokumenten:\n{events_text}",
    ),
    ("human", "Erstelle die Master-Chronologie mit Gap-Analyse."),
])


# ── DB-Persistenz ──────────────────────────────────────────────────────────────


def _persist_timeline(case_uuid: _uuid.UUID, events: List[MasterEvent]) -> None:
    """
    Ersetzt alle AI-Events in der DB durch die neue Master-Timeline.

    Strategie:
    - DELETE alle ChronologyEvent mit source_type='ai' für diesen Case
    - INSERT neue Events aus der Master-Timeline
    - User-Events (source_type='user') werden nie berührt
    - Setzt case.status = 'TIMELINE_READY'
    """
    from app.domain.models.db import Case, ChronologyEvent

    with get_db_context() as db:
        # Nur AI-Events löschen (User-Events bleiben erhalten)
        db.query(ChronologyEvent).filter(
            ChronologyEvent.case_id == case_uuid,
            ChronologyEvent.source_type == "ai",
        ).delete(synchronize_session=False)

        # Neue AI-Events einfügen
        for e in events:
            event_date = e.event_date  # Optional[date]
            source_doc_id = None
            if e.source_doc_id:
                try:
                    source_doc_id = _uuid.UUID(e.source_doc_id)
                except ValueError:
                    pass

            db_event = ChronologyEvent(
                id=_uuid.uuid4(),
                case_id=case_uuid,
                event_date=event_date,
                description=e.description[:500],
                source_doc_id=source_doc_id,
                source_type="ai",
                is_gap=e.is_gap,
            )
            db.add(db_event)

        # Status setzen
        case = db.query(Case).filter(Case.id == case_uuid).first()
        if case:
            case.status = "TIMELINE_READY"

        db.commit()
        logger.info("Timeline persistiert: %d AI-Events, Case %s → TIMELINE_READY.", len(events), case_uuid)


# ── Node ───────────────────────────────────────────────────────────────────────


async def node_build_master_timeline(state: AgentState) -> AgentState:
    """
    Reduce-Phase: Aggregiert Events zur Master-Timeline mit Gap-Analyse (US-4.2).
    """
    case_id = state["case_id"]
    messages = state.get("messages") or []
    events_per_doc: dict = state.get("events_per_doc") or {}

    try:
        case_uuid = _uuid.UUID(case_id)
    except (ValueError, KeyError):
        logger.error("build_master_timeline: Ungültige Case-ID %s.", case_id)
        return {**state, "current_step": "build_master_timeline_error"}

    # Alle Events flach zusammenführen
    all_events = []
    for doc_id, events in events_per_doc.items():
        for e in events:
            all_events.append(e)

    if not all_events:
        logger.warning("build_master_timeline: Keine Events für Case %s.", case_uuid)
        # Trotzdem Status setzen damit das Frontend nicht endlos pollt
        from app.domain.models.db import Case
        with get_db_context() as db:
            case = db.query(Case).filter(Case.id == case_uuid).first()
            if case:
                case.status = "TIMELINE_READY"
                db.commit()
        return {
            **state,
            "current_step": "build_master_timeline",
            "messages": messages + ["System: Keine Ereignisse gefunden – Timeline leer."],
        }

    # Ereignisse als lesbaren Text für den Prompt aufbereiten
    lines = []
    for e in all_events:
        date_str = e.get("date") or "Datum unbekannt"
        lines.append(f"- [{date_str}] {e.get('description', '')} (Dok: {e.get('source_doc_id', '')})")
    events_text = "\n".join(lines)

    logger.info("build_master_timeline: %d Events → gpt-4o Reduce-Call für Case %s.", len(all_events), case_uuid)

    try:
        llm = _get_llm()
        chain = _REDUCE_PROMPT | llm.with_structured_output(MasterTimeline)
        result: MasterTimeline = await chain.ainvoke({"events_text": events_text})
    except Exception as exc:
        logger.error("build_master_timeline: LLM-Fehler: %s", exc)
        # Fallback: rohe Events unsortiert übernehmen
        result = MasterTimeline(events=[
            MasterEvent(
                event_date=_parse_date_safe(e.get("date")),
                description=e.get("description", ""),
                source_doc_id=e.get("source_doc_id"),
                is_gap=False,
            )
            for e in all_events
        ])

    _persist_timeline(case_uuid, result.events)

    gaps = sum(1 for e in result.events if e.is_gap)
    logger.info(
        "build_master_timeline: %d Events (%d Lücken) persistiert für Case %s.",
        len(result.events), gaps, case_uuid,
    )

    return {
        **state,
        "current_step": "build_master_timeline",
        "messages": messages + [
            f"System: Master-Timeline erstellt: {len(result.events)} Einträge, {gaps} Lücken erkannt."
        ],
    }


def _parse_date_safe(date_str: Optional[str]) -> Optional[date]:
    """Parst ISO-Datum-String sicher zu date oder None."""
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None
