"""LangGraph-State für den Resovva-Agenten (US-3.1–3.5)."""

import operator
from typing import Annotated, List, Optional, TypedDict


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
    network_operator: Optional[str]

    # Legacy-dict (vollständiges Pydantic-Dump für Backward-Compat)
    extracted_entities: dict

    chronology: List[ChronologyEvent]
    missing_info: List[str]   # Gap-Analysis-Ergebnisse
    dossier_ready: bool
    payment_status: str       # 'pending' | 'paid'


class AgentState(ResovvaState, total=False):
    """ResovvaState + optionaler Schritt-Tracker für LangGraph-Nodes."""

    current_step: str  # load_docs | extract | mastr_lookup | confirm | …
