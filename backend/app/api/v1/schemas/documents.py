"""
Pydantic schemas for document management.

Defines structures for document listings, upload metadata, deletion
confirmations, and AI-generated summaries.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


# ── Document Entry Schemas ───────────────────────────────────────────────────

class DocumentEntry(BaseModel):
    """Metadata for a single document in a list view."""
    document_id: str
    filename: str
    document_type: str
    ocr_status: str
    created_at: str
    masked_text_preview: Optional[str] = None


class DocumentListResponse(BaseModel):
    """Response containing a list of document entries for a case."""
    documents: List[DocumentEntry]


# ── Action Response Schemas ───────────────────────────────────────────────────

class DocumentUploadResponse(BaseModel):
    """Successful upload metadata."""
    document_id: str
    filename: str
    s3_key: str
    ocr_status: str
    status: str = "stored"


class DocumentDeleteResponse(BaseModel):
    """Confirmation of a document deletion."""
    status: str = "success"
    message: str


class SummaryResponse(BaseModel):
    """AI-generated summary of a document."""
    summary: Optional[str] = None
