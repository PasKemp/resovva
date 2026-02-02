# 02. Data Schema & Domain Models

Dieses Dokument beschreibt die zentrale Domänenmodellierung für Resovva.ai. Die Pydantic-Schemas in `backend/app/schemas/domain.py` sind die **Single Source of Truth** für LangChain und FastAPI.

---

## 1. Übersicht

| Komponente          | Beschreibung                        |
| ------------------- | ----------------------------------- |
| **Enums**           | `DocumentType`, `CaseStatus`        |
| **Atomic Elements** | `ExtractedEntity`, `ChronologyItem` |
| **Core Objects**    | `DocumentInput`, `CaseState`        |

---

## 2. Enums

- **DocumentType** – Klassifikation hochgeladener Dokumente (Rechnung, Vertrag, E-Mail, Mahnung, Technisch, Unbekannt).
- **CaseStatus** – Lebenszyklus eines Falls (Draft → Analyzing → Waiting for User → Payment Pending → Completed).

---

## 3. Implementierung: `backend/app/schemas/domain.py`

```python
from enum import Enum
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel, Field, HttpUrl

# --- Enums ---
class DocumentType(str, Enum):
    INVOICE = "invoice"           # Jahresabrechnung/Abschlag
    CONTRACT = "contract"         # Vertragsunterlagen
    CORRESPONDENCE = "mail"       # E-Mail Verkehr/Briefe
    REMINDER = "reminder"         # Mahnung
    TECHNICAL = "technical"       # z.B. Ablesekarte
    UNKNOWN = "unknown"

class CaseStatus(str, Enum):
    DRAFT = "draft"
    ANALYZING = "analyzing"
    WAITING_FOR_USER = "waiting_for_user" # Gap Analysis
    PAYMENT_PENDING = "payment_pending"
    COMPLETED = "completed"

# --- Atomic Elements ---
class ExtractedEntity(BaseModel):
    """Daten, die das LLM aus Dokumenten zieht"""
    malo_id: Optional[str] = Field(None, description="Marktlokations-ID")
    meter_number: Optional[str] = Field(None, description="Zählernummer")
    amount_disputed: Optional[float] = Field(None, description="Streitiger Betrag in EUR")
    contract_start: Optional[date] = None
    contract_end: Optional[date] = None

class ChronologyItem(BaseModel):
    """Ein Eintrag im 'Roten Faden'"""
    date: date
    source_doc_id: str
    summary: str = Field(..., description="1 Satz Zusammenfassung des Events")
    original_quote: Optional[str] = Field(None, description="Zitat aus dem Dokument")
    is_missing_doc: bool = Field(False, description="True wenn das Event nur referenziert wurde (Lücke)")

# --- Core Objects ---
class DocumentInput(BaseModel):
    """Metadaten eines hochgeladenen Files"""
    id: str
    filename: str
    content_text: str  # Output from OCR
    upload_date: datetime = Field(default_factory=datetime.now)

class CaseState(BaseModel):
    """Der State für LangGraph & DB"""
    case_id: str
    user_email: Optional[str] = None
    status: CaseStatus = CaseStatus.DRAFT

    # Raw Data
    documents: List[DocumentInput] = []

    # Processed Data
    extracted_entities: ExtractedEntity = Field(default_factory=ExtractedEntity)
    chronology: List[ChronologyItem] = []

    # Logic
    missing_info_requests: List[str] = Field([], description="Fragen an den User")

    class Config:
        from_attributes = True
```

---

## 4. Verwendung

- **LangChain/LangGraph:** `CaseState` als Graph-State; `ExtractedEntity` und `ChronologyItem` als strukturierte LLM-Outputs.
- **FastAPI:** Gleiche Modelle für Request/Response-Validierung und API-Dokumentation.
