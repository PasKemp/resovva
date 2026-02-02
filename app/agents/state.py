from typing import TypedDict, List, Optional, Annotated
import operator

class DocumentMetadata(TypedDict):
    id: str
    filename: str
    type: str  # 'invoice', 'contract', 'email'

class ChronologyEvent(TypedDict):
    date: str
    description: str
    source_doc_id: str

class ResovvaState(TypedDict):
    case_id: str
    # Messages werden append-only behandelt
    messages: Annotated[List[str], operator.add]
    documents: List[DocumentMetadata]
    extracted_entities: dict  # MaLo, Zählernummer, etc.
    chronology: List[ChronologyEvent]
    missing_info: List[str]   # Gap Analysis Result
    dossier_ready: bool
    payment_status: str       # 'pending', 'paid'


class AgentState(ResovvaState, total=False):
    """ResovvaState + optional current_step für LangGraph-Nodes."""
    current_step: str  # ingest | extract | chronology | gaps
