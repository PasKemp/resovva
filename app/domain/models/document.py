"""Document-related domain models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Klassifikation hochgeladener Dokumente."""

    INVOICE = "invoice"  # Jahresabrechnung/Abschlag
    CONTRACT = "contract"  # Vertragsunterlagen
    CORRESPONDENCE = "mail"  # E-Mail Verkehr/Briefe
    REMINDER = "reminder"  # Mahnung
    TECHNICAL = "technical"  # z.B. Ablesekarte
    UNKNOWN = "unknown"


class ExtractedEntity(BaseModel):
    """Daten, die das LLM aus Dokumenten zieht."""

    malo_id: Optional[str] = Field(None, description="Marktlokations-ID")
    meter_number: Optional[str] = Field(None, description="Zählernummer")
    amount_disputed: Optional[float] = Field(None, description="Streitiger Betrag in EUR")
    contract_start: Optional[str] = None  # date als ISO-String für JSON
    contract_end: Optional[str] = None


class DocumentInput(BaseModel):
    """Metadaten eines hochgeladenen Files."""

    id: str
    filename: str
    content_text: str  # Output from OCR
    upload_date: datetime = Field(default_factory=datetime.now)
    document_type: DocumentType = DocumentType.UNKNOWN
