"""
_node_extract – RAG-gestützte Entitäten-Extraktion (US-3.2).

Strikt gpt-4o-mini (kein Modell-Wechsel ohne Ticket).
3 separate Qdrant-Suchen → fusionierter Kontext → ExtractedEntity.
Fallback auf messages[-1] wenn RAG keine Treffer liefert.
"""

from __future__ import annotations

import logging

from langchain_core.prompts import ChatPromptTemplate

from app.agents.state import AgentState
from app.core.rag import search_rag
from app.domain.models.document import ExtractedEntity

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Du bist ein präziser Assistent für deutsche Energiestreit-Fälle. "
            "Extrahiere aus den folgenden Textpassagen genau diese Felder:\n"
            "- malo_id: Marktlokations-ID (begins mit DE, 33 Zeichen)\n"
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

    # api_key nur übergeben wenn explizit gesetzt – sonst liest das OpenAI SDK
    # OPENAI_API_KEY direkt aus dem Environment (Fallback-Mechanismus des SDK).
    kwargs = {}
    if settings.openai_api_key:
        kwargs["api_key"] = settings.openai_api_key

    return ChatOpenAI(model="gpt-4o-mini", temperature=0, timeout=60, **kwargs)


async def node_extract(state: AgentState) -> AgentState:
    """
    LangGraph-Node: Entitäten aus Dokumenten extrahieren.

    Führt 3 zielgerichtete RAG-Suchen durch (US-3.2):
      - Zählernummer
      - Marktlokation (MaLo)
      - Offener Betrag / Forderung
    Fusioniert die Ergebnisse und übergibt den Kontext an gpt-4o-mini.
    """
    case_id = state["case_id"]
    messages = state.get("messages") or []

    # ── RAG-Suchen ─────────────────────────────────────────────────────────────
    rag_queries = [
        "Zählernummer Stromzähler Gaszähler Messstellenbetreiber",
        "Marktlokation MaLo ID DE Marktstammdatenregister",
        "offener Betrag Forderung EUR Streitwert Rückstand",
    ]
    context_chunks: list[str] = []
    for query in rag_queries:
        hits = search_rag(query, case_id, limit=3)
        context_chunks.extend(hits)

    # Fallback: RAG leer → nutze den kompletten Dokument-Corpus aus messages
    if not context_chunks:
        logger.warning("RAG: keine Treffer für Case %s – Fallback auf message-Corpus.", case_id)
        context_chunks = [messages[-1]] if messages else ["Kein Text verfügbar."]

    context = "\n\n---\n\n".join(context_chunks[:9])  # max ~9 000 Tokens Kontext

    # ── LLM-Extraktion ─────────────────────────────────────────────────────────
    try:
        llm = _get_mini_llm()
        chain = _EXTRACT_PROMPT | llm.with_structured_output(ExtractedEntity)
        result: ExtractedEntity = await chain.ainvoke({"context": context})

        logger.info(
            "Extraktion Case %s: MaLo=%s Zähler=%s Betrag=%s",
            case_id,
            result.malo_id,
            result.meter_number,
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
