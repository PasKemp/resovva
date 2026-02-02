"""Case domain models."""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from app.domain.models.document import DocumentInput, ExtractedEntity
from app.domain.models.timeline import ChronologyItem


class CaseStatus(str, Enum):
    """Lebenszyklus eines Falls."""

    DRAFT = "draft"
    ANALYZING = "analyzing"
    WAITING_FOR_USER = "waiting_for_user"  # Gap Analysis
    PAYMENT_PENDING = "payment_pending"
    COMPLETED = "completed"


class CaseState(BaseModel):
    """Der State für LangGraph & DB."""

    case_id: str
    user_email: Optional[str] = None
    status: CaseStatus = CaseStatus.DRAFT

    # Raw Data
    documents: List[DocumentInput] = []

    # Processed Data
    extracted_entities: ExtractedEntity = Field(default_factory=ExtractedEntity)
    chronology: List[ChronologyItem] = []

    # Logic
    missing_info_requests: List[str] = Field(
        default_factory=list,
        description="Fragen an den User",
    )

    model_config = {"from_attributes": True}
