"""
Pydantic schemas for the mobile QR-code upload flow.

Defines structures for temporary upload tokens and document submission
from mobile devices.
"""

from __future__ import annotations


from pydantic import BaseModel


# ── Token Management Schemas ──────────────────────────────────────────────────

class CreateTokenRequest(BaseModel):
    """Request to generate a temporary mobile upload token for a case."""
    case_id: str


class TokenResponse(BaseModel):
    """Temporary token metadata for client-side QR generation."""
    token: str
    expires_at: str
    upload_url: str


class TokenInfoResponse(BaseModel):
    """Validation status for a mobile upload token."""
    case_id: str
    expires_at: str
    valid: bool


# ── Upload Status Schemas ─────────────────────────────────────────────────────

class MobileUploadResponse(BaseModel):
    """Metadata for a successful mobile upload."""
    document_id: str
    filename: str
    ocr_status: str
    status: str = "stored"
