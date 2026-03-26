"""
_node_detect_opponent – Streitpartei-Erkennung via RAG + LLM (US-9.1).

Erkennt Kategorie und Namen der Gegenseite aus Briefköpfen, Absenderzeilen
und Fußzeilen der hochgeladenen Dokumente.

Kategorien:
  strom | gas | wasser | versicherung | mobilfunk_internet
  amt_behoerde | vermieter_immobilien | sonstiges

Confidence-Logik:
  1.0 – eindeutig im Briefkopf gefunden
  0.5 – nur aus Kontext erschlossen
  0.0 – nicht gefunden
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.agents.state import AgentState
from app.core.rag import search_rag

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {
    "strom", "gas", "wasser", "versicherung",
    "mobilfunk_internet", "amt_behoerde", "vermieter_immobilien", "sonstiges",
}

_DETECT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "Du bist ein präziser Assistent für deutsche Verbraucherstreitigkeiten. "
        "Analysiere die folgenden Texte und ermittle die Streitpartei (die Gegenseite).\n\n"
        "Verfügbare Kategorien:\n"
        "- strom: Stromversorger oder Netzbetreiber\n"
        "- gas: Gasversorger oder Netzbetreiber\n"
        "- wasser: Wasserversorger\n"
        "- versicherung: Versicherungsunternehmen (z.B. Allianz, AOK, TK)\n"
        "- mobilfunk_internet: Mobilfunk- oder Internetanbieter (z.B. Telekom, Vodafone, 1&1)\n"
        "- amt_behoerde: Ämter, Behörden, öffentliche Stellen (z.B. Finanzamt, Jobcenter)\n"
        "- vermieter_immobilien: Vermieter, Hausverwaltung oder Immobiliengesellschaft\n"
        "- sonstiges: Alle anderen Streitparteien\n\n"
        "WICHTIG:\n"
        "- category: immer genau eine der 8 Kategorien zurückgeben\n"
        "- name: Firmen-/Behördenname aus Briefkopf oder Absenderzeile – null wenn unklar\n"
        "- confidence: 1.0 wenn eindeutig im Briefkopf, 0.5 wenn aus Kontext erschlossen, "
        "0.0 wenn nicht erkennbar\n\n"
        "Texte:\n{context}",
    ),
    ("human", "Erkenne Kategorie und Name der Streitpartei."),
])


class OpponentDetectionResult(BaseModel):
    """Strukturierte LLM-Ausgabe für die Streitparteien-Erkennung."""

    category: str = Field(description="Eine der 8 Kategorien")
    name: Optional[str] = Field(None, description="Name der Streitpartei oder null")
    confidence: float = Field(0.0, description="Confidence-Score 0.0–1.0")


def _get_mini_llm():
    """Liefert gpt-4o-mini (DEV: OpenAI, PROD: Azure)."""
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


async def node_detect_opponent(state: AgentState) -> AgentState:
    """
    LangGraph-Node: Streitpartei erkennen (US-9.1).

    Führt 3 gezielte RAG-Suchen durch:
      1. Briefkopf / Absender / Firmenname
      2. Vertragspartner / Auftraggeber
      3. Kategorie-spezifische Keywords (Strom, Versicherung, Behörde …)
    Fusioniert die Ergebnisse und übergibt den Kontext an gpt-4o-mini.
    """
    case_id = state["case_id"]
    messages = state.get("messages") or []

    rag_queries = [
        "Absender Briefkopf Firmensitz Unternehmen GmbH AG Stadtwerke",
        "Vertragspartner Auftraggeber Dienstleister Vermieter Behörde Amt",
        "Versicherung Mobilfunk Internet Strom Gas Wasser Netznutzung Miete",
    ]
    context_chunks: list[str] = []
    for query in rag_queries:
        hits = search_rag(query, case_id, limit=3)
        context_chunks.extend(hits)

    if not context_chunks:
        logger.warning("detect_opponent: kein RAG-Treffer für Case %s – Fallback.", case_id)
        context_chunks = [messages[-1]] if messages else ["Kein Text verfügbar."]

    context = "\n\n---\n\n".join(context_chunks[:9])

    try:
        llm = _get_mini_llm()
        chain = _DETECT_PROMPT | llm.with_structured_output(OpponentDetectionResult)
        result: OpponentDetectionResult = await chain.ainvoke({"context": context})

        # Kategorie validieren – bei ungültigem Wert sicher auf "sonstiges" fallen
        category = result.category if result.category in VALID_CATEGORIES else "sonstiges"
        confidence = max(0.0, min(1.0, float(result.confidence)))

        logger.info(
            "Streitpartei Case %s: Kategorie=%s Name=%r Confidence=%.2f",
            case_id, category, result.name, confidence,
        )
        return {
            **state,
            "current_step": "detect_opponent",
            "opponent_category": category,
            "opponent_name": result.name,
            "opponent_confidence": confidence,
            "messages": messages + [
                f"System: Streitpartei – Kategorie: {category}, "
                f"Name: {result.name}, Confidence: {confidence:.2f}"
            ],
        }
    except Exception as exc:
        logger.warning(
            "Streitparteien-Erkennung fehlgeschlagen (Case %s): %s – Fallback auf 'sonstiges'.",
            case_id, exc,
        )
        return {
            **state,
            "current_step": "detect_opponent",
            "opponent_category": "sonstiges",
            "opponent_name": None,
            "opponent_confidence": 0.0,
            "messages": messages + [
                f"System: Streitparteien-Erkennung fehlgeschlagen: {exc}"
            ],
        }
