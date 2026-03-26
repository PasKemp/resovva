"""
_node_extract – RAG-gestützte Entitäten-Extraktion (US-3.2, US-9.2).

Strikt gpt-4o-mini (kein Modell-Wechsel ohne Ticket).
3 separate Qdrant-Suchen → fusionierter Kontext → ExtractedEntity.
Fallback auf messages[-1] wenn RAG keine Treffer liefert.

US-9.2: Jedes extrahierte Feld erhält einen Confidence-Score:
  1.0 – Regex-Muster eindeutig gematcht (MaLo: DE + 33 Zeichen)
  0.8 – Alphanumerisches Muster erkannt (Zählernummer)
  0.85 – Numerischer Betrag gefunden
  0.6  – LLM-Extraktion ohne Regex-Bestätigung
  0.0  – Wert ist null
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate

from app.agents.state import AgentState
from app.core.rag import search_rag_with_meta
from app.domain.models.document import ExtractedEntity

logger = logging.getLogger(__name__)

# Regex für MaLo-ID: beginnt mit DE, genau 33 Zeichen
_MALO_RE = re.compile(r"^DE[A-Z0-9]{31}$")
# Regex für Zählernummer: ≥4 alphanumerische Zeichen
_METER_RE = re.compile(r"^[A-Z0-9]{4,}", re.IGNORECASE)

_EXTRACT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Du bist ein präziser Assistent für deutsche Energiestreit-Fälle. "
            "Extrahiere aus den folgenden Textpassagen genau diese Felder:\n"
            "- malo_id: Marktlokations-ID (beginnt mit DE, 33 Zeichen)\n"
            "- meter_number: Zählernummer (alphanumerisch)\n"
            "- amount_disputed: Streitiger Betrag in EUR (nur Zahl)\n"
            "- contract_start / contract_end: ISO-Datum oder null\n\n"
            "WICHTIG: Bei Unsicherheit null zurückgeben, NIEMALS raten.\n\n"
            "Texte:\n{context}",
        ),
        ("human", "Extrahiere die Entitäten aus den obigen Texten."),
    ]
)


def _get_mini_llm():
    """
    Liefert strikt gpt-4o-mini (US-3.2: kein teureres Modell).

    Azure-Prod: Deployment 'gpt-4o-mini' muss im Azure-Portal angelegt sein.
    DEV: platform.openai.com model='gpt-4o-mini'.
    """
    from app.core.config import get_settings

    settings = get_settings()
    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint.rstrip("/"),
            api_key=settings.azure_openai_api_key,
            azure_deployment="gpt-4o-mini",
            openai_api_version=settings.openai_api_version,
            temperature=0,
            timeout=60,
        )

    from langchain_openai import ChatOpenAI

    kwargs = {}
    if settings.openai_api_key:
        kwargs["api_key"] = settings.openai_api_key

    return ChatOpenAI(model="gpt-4o-mini", temperature=0, timeout=60, **kwargs)


def _compute_confidence(value: Optional[object], field: str) -> float:
    """
    Berechnet den Confidence-Score für ein extrahiertes Feld (US-9.2).

    Score-Logik:
      MaLo:        1.0 wenn Regex matched, 0.6 wenn LLM-only ohne Regex
      Zählernr.:   0.8 wenn Muster erkannt, 0.6 sonst
      Betrag:      0.85
      Sonstige:    0.6
      null:        0.0
    """
    if value is None:
        return 0.0
    s = str(value)
    if field == "malo_id":
        return 1.0 if _MALO_RE.match(s) else 0.6
    if field == "meter_number":
        return 0.8 if _METER_RE.match(s) else 0.6
    if field == "amount_disputed":
        return 0.85
    return 0.6


def _find_source(
    value: Optional[object],
    rag_results: list[dict],
) -> tuple[Optional[str], Optional[str]]:
    """
    Sucht den extrahierten Wert in den RAG-Treffern (US-9.2).

    Returns:
        (document_id, snippet) – beide None wenn nicht gefunden.
    """
    if value is None:
        return None, None
    needle = str(value)
    for r in rag_results:
        text = r.get("text", "")
        idx = text.find(needle)
        if idx >= 0:
            start = max(0, idx - 75)
            end = min(len(text), idx + len(needle) + 75)
            snippet = text[start:end].strip()[:150]
            return r.get("document_id"), snippet
    return None, None


async def node_extract(state: AgentState) -> AgentState:
    """
    LangGraph-Node: Entitäten aus Dokumenten extrahieren (US-3.2, US-9.2).

    Führt 3 zielgerichtete RAG-Suchen durch:
      - Zählernummer
      - Marktlokation (MaLo)
      - Offener Betrag / Forderung
    Fusioniert die Ergebnisse, übergibt den Kontext an gpt-4o-mini und
    berechnet Confidence-Scores für jedes Feld.
    """
    case_id = state["case_id"]
    messages = state.get("messages") or []

    # ── RAG-Suchen mit Metadaten ────────────────────────────────────────────
    rag_queries = [
        "Zählernummer Stromzähler Gaszähler Messstellenbetreiber",
        "Marktlokation MaLo ID DE Marktstammdatenregister",
        "offener Betrag Forderung EUR Streitwert Rückstand",
    ]
    rag_results: list[dict] = []
    for query in rag_queries:
        hits = search_rag_with_meta(query, case_id, limit=3)
        rag_results.extend(hits)

    context_chunks = [r["text"] for r in rag_results]

    if not context_chunks:
        logger.warning("RAG: keine Treffer für Case %s – Fallback auf message-Corpus.", case_id)
        context_chunks = [messages[-1]] if messages else ["Kein Text verfügbar."]
        rag_results = []

    context = "\n\n---\n\n".join(context_chunks[:9])

    # ── LLM-Extraktion ──────────────────────────────────────────────────────
    try:
        llm = _get_mini_llm()
        chain = _EXTRACT_PROMPT | llm.with_structured_output(ExtractedEntity)
        result: ExtractedEntity = await chain.ainvoke({"context": context})

        # ── Confidence-Scores berechnen (US-9.2) ───────────────────────────
        fields_to_score = {
            "malo_id": result.malo_id,
            "meter_number": result.meter_number,
            "amount_disputed": result.amount_disputed,
        }
        field_confidences: dict = {}
        source_snippets: dict = {}
        source_doc_ids: dict = {}

        for field_name, field_value in fields_to_score.items():
            field_confidences[field_name] = _compute_confidence(field_value, field_name)
            doc_id, snippet = _find_source(field_value, rag_results)
            if doc_id:
                source_doc_ids[field_name] = doc_id
            if snippet:
                source_snippets[field_name] = snippet

        logger.info(
            "Extraktion Case %s: MaLo=%s (conf=%.2f) Zähler=%s (conf=%.2f) Betrag=%s",
            case_id,
            result.malo_id,
            field_confidences.get("malo_id", 0.0),
            result.meter_number,
            field_confidences.get("meter_number", 0.0),
            result.amount_disputed,
        )
        return {
            **state,
            "current_step": "extract",
            "meter_number": result.meter_number,
            "malo_id": result.malo_id,
            "dispute_amount": result.amount_disputed,
            "currency": "EUR" if result.amount_disputed is not None else None,
            "extracted_entities": result.model_dump(),
            "field_confidences": {
                **state.get("field_confidences", {}),
                **field_confidences,
            },
            "source_snippets": {
                **state.get("source_snippets", {}),
                **source_snippets,
            },
            "source_doc_ids": {
                **state.get("source_doc_ids", {}),
                **source_doc_ids,
            },
            "messages": messages + [
                f"System: Extraktion – MaLo: {result.malo_id}, "
                f"Zähler: {result.meter_number}, Betrag: {result.amount_disputed}"
            ],
        }
    except Exception as exc:
        logger.error("Extraktion fehlgeschlagen (Case %s): %s", case_id, exc)
        return {
            **state,
            "current_step": "extract_error",
            "messages": messages + [f"System: Extraktion fehlgeschlagen: {exc}"],
        }


def check_missing_data(state: AgentState) -> str:
    """
    Conditional Edge nach Extraktion (US-3.3).

    Sind BEIDE Kerndaten (meter_number UND malo_id) null → 'missing_data'.
    Sonst → 'mastr_lookup'.
    """
    if state.get("meter_number") is None and state.get("malo_id") is None:
        logger.info("Case %s: Kerndaten fehlen – Early-Exit zu WAITING_FOR_USER.", state["case_id"])
        return "missing_data"
    return "mastr_lookup"
