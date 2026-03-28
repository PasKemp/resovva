"""
Pydantic schemas for case management and analysis.

Defines the structure for case listings, creation, analysis requests,
and the human-in-the-loop (HiTL) confirmation process.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ── Case Overview Schemas ─────────────────────────────────────────────────────

class CaseSummary(BaseModel):
    """Basic overview of a single case for dashboard listings."""
    case_id: str
    created_at: str
    status: str
    network_operator: Optional[str] = None
    document_count: int


class CaseListResponse(BaseModel):
    """Response containing a list of case summaries."""
    cases: List[CaseSummary]


# ── Action Response Schemas ───────────────────────────────────────────────────

class CaseCreateResponse(BaseModel):
    """Result of creating a new case."""
    case_id: str
    status: str
    message: str


class CaseDeleteResponse(BaseModel):
    """Result of deleting a case."""
    status: str = "success"
    message: str


class CaseAnalyzeResponse(BaseModel):
    """Result of starting an asynchronous analysis."""
    status: str = "accepted"
    message: str


# ── Analysis & Extraction Schemas ─────────────────────────────────────────────

class AnalysisResultResponse(BaseModel):
    """
    Status and raw result of the AI analysis.
    
    Status can be 'analyzing', 'waiting_for_user', or 'error'.
    """
    status: str
    extracted_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class ConfirmAnalysisRequest(BaseModel):
    """
    Request for HiTL confirmation (US-3.5).
    
    Allows correcting extracted entities and providing missing data.
    """
    meter_number: Optional[str] = None
    malo_id: Optional[str] = None
    dispute_amount: Optional[float] = None
    network_operator: Optional[str] = None
    opponent_category: Optional[str] = None
    opponent_name: Optional[str] = None


class ConfirmAnalysisResponse(BaseModel):
    """Response after user confirmation of analysis results."""
    status: str = "confirmed"
    next_step: str


class CaseStatusResponse(BaseModel):
    """Current processing status of documents within a case."""
    status: str
    total: int
    completed: int
    preview: Optional[str] = None


# ── Advanced Extraction Schemas (Epic 9) ──────────────────────────────────────

class ExtractionFieldResponse(BaseModel):
    """
    Metadata for a single extracted field (US-9.2).
    
    Includes confidence scores and source markers.
    """
    key: str
    value: Optional[Any] = None
    confidence: float = 0.0
    needs_review: bool = True
    auto_accepted: bool = False
    source_document_id: Optional[str] = None
    source_text_snippet: Optional[str] = None
    field_ignored: bool = False


class OpponentResponse(BaseModel):
    """Extracted opponent classification (US-9.1)."""
    category: Optional[str] = None
    name: Optional[str] = None
    confidence: float = 0.0
    needs_review: bool = True


class ExtractionResultResponse(BaseModel):
    """Detailed view of extraction results including field-level confidence."""
    fields: List[ExtractionFieldResponse]
    opponent: OpponentResponse


class UpdateOpponentRequest(BaseModel):
    """Manual correction for opponent details."""
    opponent_category: Optional[str] = None
    opponent_name: Optional[str] = None


class UpdateOpponentResponse(BaseModel):
    """Status of the opponent update."""
    status: str = "updated"
