"""Timeline/Chronology domain models."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class ChronologyItem(BaseModel):
    """Ein Eintrag im 'Roten Faden'."""

    date: date
    source_doc_id: str
    summary: str = Field(..., description="1 Satz Zusammenfassung des Events")
    original_quote: Optional[str] = Field(None, description="Zitat aus dem Dokument")
    is_missing_doc: bool = Field(
        False,
        description="True wenn das Event nur referenziert wurde (Lücke)",
    )
