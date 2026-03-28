"""
LangGraph-Graph – EPIC 3 & EPIC 9: KI-Analyse & Extraktion.

Flow:
  load_docs → detect_opponent → extract → [check_missing] → mastr_lookup
                                            ↘ missing_data → END (WAITING_FOR_USER via DB)
                                                               ↓
                                                       [interrupt_before confirm]
                                                               ↓
                                                            confirm → END

detect_opponent (US-9.1): Erkennt Streitpartei-Kategorie und Namen.
Interrupt-Punkt: vor 'confirm' (US-3.5 Human-in-the-Loop).
Resume: POST /cases/{case_id}/analysis/confirm → graph.ainvoke(None, config)
"""

from __future__ import annotations

import logging
import uuid as _uuid

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.nodes.build_master_timeline import node_build_master_timeline
from app.agents.nodes.detect_opponent import node_detect_opponent
from app.agents.nodes.extract import check_missing_data, node_extract
from app.agents.nodes.extract_events import node_extract_events
from app.agents.nodes.mastr_lookup import node_mastr_lookup
from app.agents.state import AgentState

logger = logging.getLogger(__name__)


# ── Load-Docs-Node ─────────────────────────────────────────────────────────────


async def _node_load_docs(state: AgentState) -> AgentState:
    """
    Lädt maskierte Texte aller abgeschlossenen Dokumente des Falls aus der DB.

    Legt den vollständigen Dokument-Corpus als letzten messages-Eintrag ab –
    dient als Fallback wenn Qdrant/RAG nicht erreichbar ist.
    """
    from app.domain.models.db import Document
    from app.infrastructure.database import get_db_context

    messages = state.get("messages") or []
    try:
        case_uuid = _uuid.UUID(state["case_id"])
    except (ValueError, KeyError):
        return {
            **state,
            "current_step": "load_error",
            "messages": messages + ["System: Ungültige Case-ID."],
        }

    with get_db_context() as db:
        docs = (
            db.query(Document)
            .filter(
                Document.case_id == case_uuid,
                Document.ocr_status == "completed",
                Document.masked_text.isnot(None),
            )
            .all()
        )

    if not docs:
        logger.warning("load_docs: Keine abgeschlossenen Dokumente für Case %s.", case_uuid)
        return {
            **state,
            "current_step": "load_error",
            "messages": messages + ["System: Keine verarbeiteten Dokumente gefunden."],
        }

    corpus = "\n\n".join(f"--- {d.filename} ---\n{d.masked_text}" for d in docs)
    logger.info("load_docs: %d Dokumente für Case %s geladen.", len(docs), case_uuid)

    return {
        **state,
        "current_step": "load_docs",
        "messages": messages + [corpus],
    }


# ── Confirm-Node ───────────────────────────────────────────────────────────────


async def _node_confirm(state: AgentState) -> AgentState:
    """
    Speichert die vom Nutzer bestätigten Daten in case.extracted_data.

    Wird nach dem Human-in-the-Loop-Interrupt ausgeführt (US-3.5).
    Die bestätigten skalaren Felder im State wurden durch
    graph.update_state() vom Resume-Endpoint gesetzt.
    """
    from app.domain.models.db import Case
    from app.infrastructure.database import get_db_context
    from datetime import datetime, timezone

    case_id = state["case_id"]
    messages = state.get("messages") or []

    try:
        case_uuid = _uuid.UUID(case_id)
    except ValueError:
        return state

    confirmed = {
        "meter_number": state.get("meter_number"),
        "malo_id": state.get("malo_id"),
        "dispute_amount": state.get("dispute_amount"),
        "currency": state.get("currency"),
        "network_operator": state.get("network_operator"),
        "opponent_category": state.get("opponent_category"),
        "opponent_name": state.get("opponent_name"),
        "field_confidences": state.get("field_confidences") or {},
        "source_snippets": state.get("source_snippets") or {},
        "source_doc_ids": state.get("source_doc_ids") or {},
        "confirmed": True,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }

    with get_db_context() as db:
        case = db.query(Case).filter(Case.id == case_uuid).first()
        if case:
            case.extracted_data = confirmed
            case.opponent_category = state.get("opponent_category")
            case.opponent_name = state.get("opponent_name")
            # Status zurücksetzen (Epic 4 wird hier weiterführen)
            case.status = "DRAFT"
            db.commit()
            logger.info("Case %s: Daten bestätigt und gespeichert.", case_uuid)

    return {
        **state,
        "current_step": "confirmed",
        "messages": messages + ["System: Daten vom Nutzer bestätigt und gespeichert."],
    }


# ── Missing-Data-Handler ───────────────────────────────────────────────────────


async def _node_missing_data(state: AgentState) -> AgentState:
    """
    Setzt case.status = WAITING_FOR_USER und speichert leere extracted_data.
    Wird traversiert wenn BEIDE Kerndaten (MaLo + Zähler) fehlen (US-3.3).
    """
    from datetime import datetime, timezone

    from app.domain.models.db import Case
    from app.infrastructure.database import get_db_context

    case_id = state["case_id"]
    messages = state.get("messages") or []

    try:
        case_uuid = _uuid.UUID(case_id)
    except ValueError:
        return state

    with get_db_context() as db:
        case = db.query(Case).filter(Case.id == case_uuid).first()
        if case:
            case.extracted_data = {
                "meter_number": None,
                "malo_id": None,
                "dispute_amount": state.get("dispute_amount"),
                "currency": state.get("currency"),
                "network_operator": None,
                "opponent_category": state.get("opponent_category"),
                "opponent_name": state.get("opponent_name"),
                "opponent_confidence": state.get("opponent_confidence", 0.0),
                "field_confidences": state.get("field_confidences") or {},
                "source_snippets": state.get("source_snippets") or {},
                "source_doc_ids": state.get("source_doc_ids") or {},
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "confirmed": False,
                "missing_data": True,
            }
            case.opponent_category = state.get("opponent_category")
            case.opponent_name = state.get("opponent_name")
            case.status = "WAITING_FOR_USER"
            db.commit()
            logger.info("Case %s: fehlende Kerndaten – Status → WAITING_FOR_USER.", case_uuid)

    return {
        **state,
        "current_step": "missing_data",
        "messages": messages + [
            "System: Zählernummer und MaLo-ID nicht gefunden. Nutzer-Eingabe erforderlich."
        ],
    }


# ── Graph-Builder ──────────────────────────────────────────────────────────────


def build_graph(checkpointer) -> CompiledStateGraph:
    """
    Erstellt und kompiliert den LangGraph-Analyseagenten.

    Args:
        checkpointer: AsyncPostgresSaver (Prod) oder MemorySaver (Dev/Tests).

    interrupt_before=["confirm"]:
      Nach mastr_lookup pausiert der Graph vor _node_confirm.
      Resume via: graph.update_state(config, confirmed_data) + graph.ainvoke(None, config)
    """
    graph = StateGraph(AgentState)

    graph.add_node("load_docs",             _node_load_docs)
    graph.add_node("detect_opponent",       node_detect_opponent)  # US-9.1
    graph.add_node("extract",               node_extract)
    graph.add_node("missing_data",          _node_missing_data)
    graph.add_node("mastr_lookup",          node_mastr_lookup)
    graph.add_node("confirm",               _node_confirm)
    graph.add_node("extract_events",        node_extract_events)        # US-4.1
    graph.add_node("build_master_timeline", node_build_master_timeline)  # US-4.2

    graph.set_entry_point("load_docs")
    graph.add_edge("load_docs", "detect_opponent")
    graph.add_edge("detect_opponent", "extract")

    # US-3.3: Early-Exit wenn beide Kerndaten fehlen
    graph.add_conditional_edges(
        "extract",
        check_missing_data,
        {
            "missing_data": "missing_data",
            "mastr_lookup": "mastr_lookup",
        },
    )
    graph.add_edge("missing_data", END)
    graph.add_edge("mastr_lookup", "confirm")

    # US-4.1 / US-4.2: Nach Bestätigung → Map → Reduce → Ende
    graph.add_edge("confirm",               "extract_events")
    graph.add_edge("extract_events",        "build_master_timeline")
    graph.add_edge("build_master_timeline", END)

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["confirm"],  # US-3.5: Human-in-the-Loop
    )


# ── Async Lazy Singleton ───────────────────────────────────────────────────────

_agent_app: CompiledStateGraph | None = None


async def get_agent_app() -> CompiledStateGraph:
    """
    Liefert den kompilierten Agenten (Lazy Init, async).

    Beim ersten Aufruf wird der Checkpointer im laufenden Event-Loop erstellt
    (AsyncPostgresSaver benötigt asyncio.get_running_loop()).
    """
    global _agent_app
    if _agent_app is None:
        from app.infrastructure.checkpointer import create_async_checkpointer

        checkpointer = await create_async_checkpointer()
        _agent_app = build_graph(checkpointer)
    return _agent_app
