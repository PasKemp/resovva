"""
Pydantic schemas for case chronology and timeline events.

Defines structures for event listing, manual additions, updates,
and incremental refresh triggers.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Response Schemas ──────────────────────────────────────────────────────────

class TimelineEventResponse(BaseModel):
    """A single event in the chronology."""
    event_id: str
    case_id: str
    event_date: Optional[str]  # ISO format "YYYY-MM-DD"
    description: str
    source_doc_id: Optional[str]
    source_type: str  # 'ai' | 'user'
    is_gap: bool


class TimelineResponse(BaseModel):
    """The complete timeline for a case."""
    status: str  # 'building' | 'ready' | 'empty'
    events: List[TimelineEventResponse]


class TimelineRefreshResponse(BaseModel):
    """Result of triggering an incremental timeline update."""
    status: str
    message: str


# ── Request Schemas ───────────────────────────────────────────────────────────

class AddEventRequest(BaseModel):
    """Data required to manually add an event."""
    event_date: date
    description: str = Field(..., min_length=1, max_length=1000)

    @field_validator("event_date")
    @classmethod
    def date_not_in_future(cls, v: date) -> date:
        """Ensure the event date is not in the future."""
        if v > date.today():
            raise ValueError("Event date cannot be in the future.")
        return v


class UpdateEventRequest(BaseModel):
    """Data for updating an existing event (all fields optional)."""
    event_date: Optional[date] = None
    description: Optional[str] = Field(None, max_length=1000)

    @field_validator("event_date")
    @classmethod
    def date_not_in_future(cls, v: Optional[date]) -> Optional[date]:
        """Ensure the event date is not in the future."""
        if v and v > date.today():
            raise ValueError("Event date cannot be in the future.")
        return v
