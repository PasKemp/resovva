"""LangGraph-State für den Resovva-Agenten (US-3.1–3.5, US-9.1–9.2)."""

import operator
from typing import Annotated, Dict, List, Optional, TypedDict


class DocumentMetadata(TypedDict):
    id: str
    filename: str
    type: str  # 'invoice', 'contract', 'email', ...


class ChronologyEvent(TypedDict):
    date: str
    description: str
    source_doc_id: str


class ResovvaState(TypedDict):
    case_id: str
    # append-only (LangGraph-Konvention für Message-Listen)
    messages: Annotated[List[str], operator.add]
    documents: List[DocumentMetadata]

    # US-3.2: extrahierte Kern-Entitäten (skalare Felder für Conditional-Edges)
    meter_number: Optional[str]
    malo_id: Optional[str]
    dispute_amount: Optional[float]
    currency: Optional[str]
    network_operator: Optional[str]  # deprecated – durch opponent_name ersetzt (Energie-Fälle)

    # US-9.1: Streitparteien-Erkennung
    opponent_category: Optional[str]   # OpponentCategory-Wert
    opponent_name: Optional[str]       # Firmenname / Behördenname
    opponent_confidence: float         # 0.0–1.0

    # US-9.2: Confidence-Scores und Quellen pro Feld
    field_confidences: Dict[str, float]  # { "malo_id": 1.0, "meter_number": 0.6, ... }
    source_snippets: Dict[str, str]      # { "malo_id": "...DE1234..." }
    source_doc_ids: Dict[str, str]       # { "malo_id": "doc-uuid" }

    # Legacy-dict (vollständiges Pydantic-Dump für Backward-Compat)
    extracted_entities: dict

    chronology: List[ChronologyEvent]
    missing_info: List[str]   # Gap-Analysis-Ergebnisse
    dossier_ready: bool
    payment_status: str       # 'pending' | 'paid'


class AgentState(ResovvaState, total=False):
    """ResovvaState + optionaler Schritt-Tracker für LangGraph-Nodes."""

    current_step: str  # load_docs | detect_opponent | extract | mastr_lookup | confirm | …
