"""
_node_mastr_lookup – Netzbetreiber via MaStR-API (US-3.4, US-9.1).

Reihenfolge:
  1. MaStR-REST-API anfragen – nur für Energie-Kategorien (strom/gas/wasser)
  2. Bei Fehler/Timeout oder nicht-Energie: RAG-Fallback
  3. Extrahierte Daten + Opponent-Info + Confidence-Scores in DB persistieren
  4. case.status = "WAITING_FOR_USER" setzen → Frontend kann pollen
"""

from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone

import httpx

from app.agents.state import AgentState
from app.core.category_field_config import is_energy_category
from app.core.rag import search_rag
from app.infrastructure.database import get_db_context

logger = logging.getLogger(__name__)

MASTR_TIMEOUT = 5  # Sekunden (US-3.4: kein Retry im MVP)


async def node_mastr_lookup(state: AgentState) -> AgentState:
    """
    LangGraph-Node: Netzbetreiber-Lookup + DB-Persistenz.

    Schreibt extracted_data in case und setzt status=WAITING_FOR_USER,
    damit das Frontend die Daten abrufen und dem Nutzer präsentieren kann.
    """
    case_id = state["case_id"]
    malo_id = state.get("malo_id")
    messages = state.get("messages") or []
    opponent_category = state.get("opponent_category") or "sonstiges"

    # 1. MaStR-API – nur für Energie-Kategorien (US-9.1)
    network_operator: str | None = None
    if malo_id and is_energy_category(opponent_category):
        network_operator = await _lookup_mastr(malo_id)

    # 2. RAG-Fallback für Energie (wenn MaStR kein Ergebnis)
    if not network_operator and is_energy_category(opponent_category):
        network_operator = await _rag_fallback(case_id)

    # opponent_name: MaStR-Ergebnis hat Vorrang, dann State, dann RAG-Fallback
    opponent_name = state.get("opponent_name")
    if network_operator and is_energy_category(opponent_category):
        opponent_name = network_operator  # MaStR ist autoritativer als LLM-Erkennung

    # Confidence für opponent: MaStR-Ergebnis ist sehr zuverlässig
    opponent_confidence = state.get("opponent_confidence", 0.0)
    if network_operator:
        opponent_confidence = 0.95

    # 3. In DB persistieren und Status setzen
    _persist_to_db(state, network_operator, opponent_name, opponent_confidence)

    return {
        **state,
        "current_step": "mastr_lookup",
        "network_operator": network_operator,
        "opponent_name": opponent_name,
        "opponent_confidence": opponent_confidence,
        "messages": messages + [
            f"System: Netzbetreiber – {network_operator or 'Nicht gefunden'}"
        ],
    }


async def _lookup_mastr(malo_id: str) -> str | None:
    """HTTP-Anfrage an die offizielle MaStR-REST-API."""
    from app.core.config import get_settings

    settings = get_settings()
    base = (settings.mastr_api_base_url or "").rstrip("/")
    url = f"{base}/api/MaStRAPI/wsdl/GetEinheitenStrom?MaStRNummer={malo_id}"
    try:
        async with httpx.AsyncClient(timeout=MASTR_TIMEOUT) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                for key in ("NetzbetreiberName", "Netzbetreiber", "betreiber", "name"):
                    if key in data and data[key]:
                        return str(data[key])[:120]
    except Exception as exc:
        logger.info("MaStR-API Fehler (MaLo %s): %s – RAG-Fallback aktiv.", malo_id, exc)
    return None


async def _rag_fallback(case_id: str) -> str | None:
    """
    Heuristik-Fallback: Netzbetreibernamen aus Dokumenten lesen (US-3.4).

    Sucht in RAG nach bekannten Betreiber-Schlüsselwörtern und extrahiert
    den nächsten sinnvollen Textausschnitt.
    """
    hits = search_rag(
        "Netzbetreiber Stadtwerke Verteilernetzbetreiber Netznutzung", case_id, limit=3
    )
    if not hits:
        return None

    combined = " ".join(hits)
    for keyword in ("Stadtwerke", "Netzbetreiber", "Verteilernetz", "Energie", "Netz GmbH"):
        idx = combined.find(keyword)
        if idx >= 0:
            snippet = combined[max(0, idx - 10) : idx + 50].strip()
            for stop in ("\n", ".", ",", ";"):
                end = snippet.find(stop)
                if 0 < end < len(snippet):
                    snippet = snippet[:end]
            return snippet[:80] or None
    return None


def _persist_to_db(
    state: AgentState,
    network_operator: str | None,
    opponent_name: str | None,
    opponent_confidence: float,
) -> None:
    """
    Speichert extrahierte Daten (inkl. Confidence-Scores und Opponent-Info)
    in case.extracted_data und setzt case.status = 'WAITING_FOR_USER'.
    """
    from app.domain.models.db import Case

    try:
        case_uuid = _uuid.UUID(state["case_id"])
    except (ValueError, KeyError):
        logger.warning("_persist_to_db: ungültige Case-ID '%s'", state.get("case_id"))
        return

    field_confidences = state.get("field_confidences") or {}
    # Opponent-Confidence zu den Feld-Scores hinzufügen
    field_confidences["opponent"] = opponent_confidence

    extracted = {
        "meter_number": state.get("meter_number"),
        "malo_id": state.get("malo_id"),
        "dispute_amount": state.get("dispute_amount"),
        "currency": state.get("currency"),
        "network_operator": network_operator,          # deprecated, Backward-Compat
        "opponent_category": state.get("opponent_category"),
        "opponent_name": opponent_name,
        "opponent_confidence": opponent_confidence,
        "field_confidences": field_confidences,
        "source_snippets": state.get("source_snippets") or {},
        "source_doc_ids": state.get("source_doc_ids") or {},
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "confirmed": False,
    }
    try:
        with get_db_context() as db:
            case = db.query(Case).filter(Case.id == case_uuid).first()
            if case:
                case.extracted_data = extracted
                case.opponent_category = state.get("opponent_category")
                case.opponent_name = opponent_name
                case.status = "WAITING_FOR_USER"
                db.commit()
                logger.info(
                    "Case %s: extracted_data gespeichert, Status → WAITING_FOR_USER.", case_uuid
                )
    except Exception as exc:
        logger.error("_persist_to_db fehlgeschlagen (Case %s): %s", state.get("case_id"), exc)
