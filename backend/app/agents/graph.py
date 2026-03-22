"""
Definition des LangGraph-Graphen (Nodes & Edges).

Two-Pass: Erst Strukturieren (Parsing, Entitäten, Chronologie, Gaps),
dann ggf. Dossier-Generierung.
"""

from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.core.security import mask_pii
from app.domain.models.document import ExtractedEntity
from app.domain.services.pdf_parsing import extract_text_from_pdf_async
from app.infrastructure.azure_openai import get_llm
from app.infrastructure.checkpointer import get_checkpointer

UPLOAD_DIR = Path("/tmp/resovva_uploads")


def _format_llm_error(exc: Exception) -> str:
    """Formatiert LLM-Fehler lesbar und mit typischen Lösungen."""
    msg = str(exc).strip() or type(exc).__name__
    hint = ""
    if "connection" in msg.lower() or "connect" in msg.lower():
        hint = " (Prüfe: OPENAI_API_KEY in .env, Internet/Proxy, bei Azure: AZURE_OPENAI_ENDPOINT ohne trailing slash)"
    elif "401" in msg or "unauthorized" in msg.lower():
        hint = " (API-Key ungültig oder abgelaufen; bei OpenAI: Billing/Guthaben prüfen)"
    elif "timeout" in msg.lower():
        hint = " (Antwort zu langsam; ggf. kürzerer Text oder Timeout in Config erhöhen)"
    return f"{msg}{hint}"


async def _node_ingest(state: AgentState) -> AgentState:
    """Node: Liest PDFs ein, extrahiert Text, maskiert PII."""
    case_id = state["case_id"]
    files = list(UPLOAD_DIR.glob(f"{case_id}_*"))

    if not files:
        messages = (state.get("messages") or []) + ["System: Keine Dateien gefunden."]
        return {**state, "current_step": "ingest_error", "messages": messages}

    processed_docs = []
    full_text_corpus = ""

    for file_path in files:
        raw_text = await extract_text_from_pdf_async(file_path)
        safe_text = mask_pii(raw_text)

        doc_meta = {
            "id": file_path.name,
            "filename": file_path.name.replace(f"{case_id}_", ""),
            "type": "unknown",
            "content_preview": safe_text[:200],
        }
        processed_docs.append(doc_meta)
        full_text_corpus += f"\n--- DOKUMENT: {doc_meta['filename']} ---\n{safe_text}\n"

    messages = (state.get("messages") or []) + [
        f"System: Ingestion abgeschlossen.\n{full_text_corpus}"
    ]

    return {
        **state,
        "documents": processed_docs,
        "current_step": "ingest",
        "messages": messages,
    }


async def _node_extract(state: AgentState) -> AgentState:
    """Node: LLM-basierte Entitäten-Extraktion (MaLo, Zähler, Beträge)."""
    messages = state.get("messages") or []
    if not messages:
        return {**state, "current_step": "extract_error"}

    context_text = messages[-1]

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Du bist ein präziser Legal-AI-Assistent. Extrahiere aus den folgenden "
            "Dokumententexten die Metadaten: Marktlokations-ID (MaLo), Zählernummer, "
            "streitiger Betrag in EUR, Vertragsbeginn/-ende. Antworte nur mit den "
            "extrahierten Feldern, fehlende Werte als null.",
        ),
        ("human", "{text}"),
    ])

    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(ExtractedEntity)
        chain = prompt | structured_llm

        extraction_result: ExtractedEntity = await chain.ainvoke({"text": context_text})

        return {
            **state,
            "current_step": "extract",
            "extracted_entities": extraction_result.model_dump(),
            "messages": messages + [
                f"AI: Extrahierte Daten: {extraction_result.model_dump_json()}"
            ],
        }
    except Exception as e:
        err_detail = _format_llm_error(e)
        return {
            **state,
            "current_step": "extract_error",
            "messages": messages + [f"System: LLM-Extraktion fehlgeschlagen: {err_detail}"],
        }


def _node_chronology(state: AgentState) -> AgentState:
    """Node: Chronologie bauen (Roter Faden)."""
    return {**state, "current_step": "chronology"}


def _node_gaps(state: AgentState) -> AgentState:
    """Node: Gap-Analysis – fehlende Belege identifizieren."""
    return {**state, "current_step": "gaps"}


def _route_after_gaps(state: AgentState) -> str:
    """Conditional: Bei fehlenden Infos auf User warten, sonst beenden."""
    missing = state.get("missing_info") or []
    if missing:
        return "wait_for_user"
    return "end"


def build_graph():
    """Erstellt den kompilierten LangGraph-Graphen mit Checkpointer."""
    graph = StateGraph(AgentState)

    graph.add_node("ingest", _node_ingest)
    graph.add_node("extract", _node_extract)
    graph.add_node("chronology", _node_chronology)
    graph.add_node("gaps", _node_gaps)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "extract")
    graph.add_edge("extract", "chronology")
    graph.add_edge("chronology", "gaps")
    graph.add_conditional_edges(
        "gaps",
        _route_after_gaps,
        {"wait_for_user": END, "end": END},
    )

    checkpointer = get_checkpointer()
    return graph.compile(checkpointer=checkpointer)
