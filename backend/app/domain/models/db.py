"""
SQLAlchemy ORM models for Resovva.

This module defines the complete database schema, including users, cases,
documents, and related metadata entities. Models use SQLAlchemy 2.0 style
Mapped typing for improved static analysis.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, String, Text
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    """
    User model for authentication and multi-tenancy.

    Attributes:
        id: Primary key (UUID).
        email: Unique user email address.
        hashed_password: Bcrypt hash of the user password.
        accepted_terms: Whether the user accepted terms of service.
        created_at: Account creation timestamp (UTC).
        first_name: User's first name.
        last_name: User's last name.
        street: Physical address (street and house number).
        postal_code: Physical address (postal code).
        city: Physical address (city).
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    accepted_terms: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Profile data
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    street: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    cases: Mapped[List["Case"]] = relationship(
        "Case", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of the User."""
        return f"<User(id={self.id!s:.8}, email={self.email!r})>"

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the User object for API responses.

        Returns:
            Dict[str, Any]: Basic user profile and status.
        """
        return {
            "user_id": str(self.id),
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "street": self.street,
            "postal_code": self.postal_code,
            "city": self.city,
            "accepted_terms": self.accepted_terms,
            "created_at": self.created_at.isoformat(),
            "profile_complete": bool(
                self.first_name and self.last_name
                and self.street and self.postal_code and self.city
            ),
        }


# ── Cases ─────────────────────────────────────────────────────────────────────

class Case(Base):
    """
    Central Case model representing a legal claim.

    Status flow: DRAFT → WAITING_FOR_USER → PAID → COMPLETED

    Attributes:
        id: Primary key (UUID).
        user_id: ForeignKey reference to User.
        status: Current workflow status.
        stripe_session_id: ID of the associated Stripe Checkout session.
        extracted_data: JSON blob of facts extracted by AI.
        opponent_category: Classification of the opposing party.
        opponent_name: Name of the opposing party.
        created_at: Timestamp of creation (UTC).
        updated_at: Timestamp of last modification (UTC).
    """

    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", index=True)
    stripe_session_id: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )
    extracted_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    initial_context: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=None)

    # Opponent details
    opponent_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    opponent_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship("User", back_populates="cases")
    documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="case", cascade="all, delete-orphan"
    )
    timeline_events: Mapped[List["ChronologyEvent"]] = relationship(
        "ChronologyEvent", back_populates="case", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """String representation of the Case."""
        return f"<Case(id={self.id!s:.8}, status={self.status!r})>"

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the Case object for API responses.

        Returns:
            Dict[str, Any]: Case overview data.
        """
        return {
            "case_id": str(self.id),
            "user_id": str(self.user_id),
            "status": self.status,
            "extracted_data": self.extracted_data,
            "document_count": len(self.documents),
            "network_operator": (self.extracted_data or {}).get("network_operator"),
            "opponent_category": self.opponent_category,
            "opponent_name": self.opponent_name,
            "initial_context": self.initial_context,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ── Documents ──────────────────────────────────────────────────────────────────

class Document(Base):
    """
    Document model for ingestion and S3 storage.

    Attributes:
        id: Primary key (UUID).
        case_id: ForeignKey reference to Case.
        filename: Original user filename.
        s3_key: Unique S3 storage path.
        document_type: Classification (INVOICE, CONTRACT, etc.).
        ocr_status: Status of the OCR pipeline.
        masked_text: PII-masked OCR output.
        ai_summary: On-demand AI-generated summary.
        created_at: Upload timestamp (UTC).
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), default="UNKNOWN")
    ocr_status: Mapped[str] = mapped_column(String(30), default="pending")
    masked_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    case: Mapped["Case"] = relationship("Case", back_populates="documents")

    def __repr__(self) -> str:
        """String representation of the Document."""
        return f"<Document(id={self.id!s:.8}, filename={self.filename!r})>"

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the Document object for API responses.

        Returns:
            Dict[str, Any]: Document metadata.
        """
        return {
            "document_id": str(self.id),
            "case_id": str(self.case_id),
            "filename": self.filename,
            "s3_key": self.s3_key,
            "document_type": self.document_type,
            "ocr_status": self.ocr_status,
            "created_at": self.created_at.isoformat(),
            "ai_summary": self.ai_summary,
            "masked_text_preview": (self.masked_text[:500] if self.masked_text else None),
        }


# ── Chronology ────────────────────────────────────────────────────────────────

class ChronologyEvent(Base):
    """
    An individual event in the chronology of a case.

    Attributes:
        id: Primary key (UUID).
        case_id: ForeignKey reference to Case.
        event_date: Date when the event occurred.
        description: Textual description of the event.
        source_doc_id: Optional reference to the supporting Document.
        source_type: 'ai' or 'user'.
        is_gap: Marker for missing evidence.
    """

    __tablename__ = "chronology_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    event_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_doc_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(20), default="ai")
    is_gap: Mapped[bool] = mapped_column(Boolean, default=False)

    case: Mapped["Case"] = relationship("Case", back_populates="timeline_events")

    def __repr__(self) -> str:
        """String representation of the Event."""
        return f"<ChronologyEvent(id={self.id!s:.8}, date={self.event_date})>"

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the Event for API responses.

        Returns:
            Dict[str, Any]: Event details and source link.
        """
        return {
            "event_id": str(self.id),
            "case_id": str(self.case_id),
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "description": self.description,
            "source_doc_id": str(self.source_doc_id) if self.source_doc_id else None,
            "source_type": self.source_type,
            "is_gap": self.is_gap,
        }


# ── Tokens & Utility ──────────────────────────────────────────────────────────

class MobileUploadToken(Base):
    """
    Short-lived token for QR-code based mobile uploads.

    Attributes:
        id: Primary key (UUID).
        case_id: ForeignKey reference to Case.
        token_hash: SHA-256 hash of the raw token.
        expires_at: Expiry timestamp.
        used: One-time use prevention.
        created_at: Creation timestamp.
    """

    __tablename__ = "mobile_upload_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<MobileUploadToken(used={self.used}, expires={self.expires_at})>"


class PasswordResetToken(Base):
    """
    Token for password reset workflow.

    Attributes:
        id: Primary key (UUID).
        user_id: ForeignKey reference to User.
        token_hash: SHA-256 hash of the raw token.
        expires_at: Expiry timestamp.
        used: One-time use prevention.
        created_at: Creation timestamp.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<PasswordResetToken(user_id={self.user_id!s:.8}, used={self.used})>"


class LlamaParseUsage(Base):
    """
    Monitoring for LlamaParse daily free-tier usage.

    Attributes:
        id: Auto-increment primary key.
        date: Day of entry.
        pages_used: Count of pages processed.
    """

    __tablename__ = "llama_parse_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    pages_used: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        """String representation."""
        return f"<LlamaParseUsage(date={self.date}, pages={self.pages_used})>"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API."""
        return {
            "date": self.date.isoformat(),
            "pages_used": self.pages_used,
        }
