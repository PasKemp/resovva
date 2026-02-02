"""
Definition des LangGraph-Graphen (Nodes & Edges).

Two-Pass: Erst Strukturieren (Parsing, Entitäten, Chronologie, Gaps),
dann ggf. Dossier-Generierung.
"""

from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.infrastructure.checkpointer import get_checkpointer


def _node_ingest(state: AgentState) -> AgentState:
    """Node: Ingestion & Parsing der Dokumente."""
    # TODO: PDF/Email parsen, Texte extrahieren
    return {**state, "current_step": "ingest"}


def _node_extract(state: AgentState) -> AgentState:
    """Node: LLM-basierte Entitäten-Extraktion (MaLo, Zähler, Beträge)."""
    # TODO: LLM-Call, structured output → extracted_entities
    return {**state, "current_step": "extract"}


def _node_chronology(state: AgentState) -> AgentState:
    """Node: Chronologie bauen (Roter Faden)."""
    # TODO: Chronology Builder aufrufen
    return {**state, "current_step": "chronology"}


def _node_gaps(state: AgentState) -> AgentState:
    """Node: Gap-Analysis – fehlende Belege identifizieren."""
    # TODO: Lücken erkennen → missing_info_requests, ggf. auf WAITING_FOR_USER
    return {**state, "current_step": "gaps"}


def build_graph():
    """Erstellt den kompilieren LangGraph-Graphen mit Checkpointer (für Resume)."""
    graph = StateGraph(AgentState)

    graph.add_node("ingest", _node_ingest)
    graph.add_node("extract", _node_extract)
    graph.add_node("chronology", _node_chronology)
    graph.add_node("gaps", _node_gaps)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "extract")
    graph.add_edge("extract", "chronology")
    graph.add_edge("chronology", "gaps")
    graph.add_edge("gaps", END)

    checkpointer = get_checkpointer()
    return graph.compile(checkpointer=checkpointer)
