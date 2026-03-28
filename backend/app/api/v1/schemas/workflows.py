"""
Pydantic schemas for LangGraph workflow orchestration.

Defines structures for manually triggering and resuming stateful agents
within the case processing pipeline.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# ── Request Schemas ───────────────────────────────────────────────────────────

class WorkflowRequest(BaseModel):
    """Initial request to start an agent thread."""
    case_id: str


class ResumeRequest(BaseModel):
    """
    Data required to resume a paused agent (HiTL).
    
    Includes entity corrections and validated metadata.
    """
    case_id: str
    meter_number: Optional[str] = None
    malo_id: Optional[str] = None
    dispute_amount: Optional[float] = None
    network_operator: Optional[str] = None
