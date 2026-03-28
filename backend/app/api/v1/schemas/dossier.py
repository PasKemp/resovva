"""
Pydantic schemas for dossier generation and delivery.

Defines the structure for dossier status polling including temporary
S3 presigned URLs.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# ── Response Schemas ──────────────────────────────────────────────────────────

class DossierStatusResponse(BaseModel):
    """
    Current status of the dossier generation process.
    
    Status values:
    - 'PAID': Payment successful, generation not yet started.
    - 'GENERATING_DOSSIER': Process is currently running.
    - 'COMPLETED': Dossier is ready, download_url is provided.
    - 'ERROR_GENERATION': An error occurred during processing.
    """
    status: str
    download_url: Optional[str] = None
    error_message: Optional[str] = None
