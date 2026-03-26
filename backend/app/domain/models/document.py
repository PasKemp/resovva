"""Document-related domain models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Klassifikation hochgeladener Dokumente."""

    INVOICE = "invoice"  # Jahresabrechnung/Abschlag
    CONTRACT = "contract"  # Vertragsunterlagen
    CORRESPONDENCE = "mail"  # E-Mail Verkehr/Briefe
    REMINDER = "reminder"  # Mahnung
    TECHNICAL = "technical"  # z.B. Ablesekarte
    UNKNOWN = "unknown"


class OpponentCategory(str, Enum):
    """Streitpartei-Kategorien (US-9.1)."""

    STROM = "strom"
    GAS = "gas"
    WASSER = "wasser"
    VERSICHERUNG = "versicherung"
    MOBILFUNK_INTERNET = "mobilfunk_internet"
    AMT_BEHOERDE = "amt_behoerde"
    VERMIETER_IMMOBILIEN = "vermieter_immobilien"
    SONSTIGES = "sonstiges"


class ExtractedField(BaseModel):
    """Extrahiertes Feld mit Confidence-Score und Quellenangabe (US-9.2)."""

    key: str
    value: Any = None
    confidence: float = 0.0
    source_document_id: Optional[str] = None
    source_text_snippet: Optional[str] = None  # max. 150 Zeichen rund um den Wert
    needs_review: bool = True    # confidence < 0.8
    auto_accepted: bool = False  # confidence >= 0.8
    field_ignored: bool = False  # Nutzer hat Feld als „Nicht relevant" markiert


class ExtractedEntity(BaseModel):
    """Daten, die das LLM aus Dokumenten zieht."""

    malo_id: Optional[str] = Field(None, description="Marktlokations-ID")
    meter_number: Optional[str] = Field(None, description="Zählernummer")
    amount_disputed: Optional[float] = Field(None, description="Streitiger Betrag in EUR")
    contract_start: Optional[str] = None  # date als ISO-String für JSON
    contract_end: Optional[str] = None
    opponent_category: Optional[str] = None  # US-9.1
    opponent_name: Optional[str] = None      # US-9.1
    opponent_confidence: float = 0.0         # US-9.1


class DocumentInput(BaseModel):
    """Metadaten eines hochgeladenen Files."""

    id: str
    filename: str
    content_text: str  # Output from OCR
    upload_date: datetime = Field(default_factory=datetime.now)
    document_type: DocumentType = DocumentType.UNKNOWN
