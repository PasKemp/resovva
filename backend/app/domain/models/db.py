"""
SQLAlchemy ORM-Modelle – Resovva Datenbankschema.

Tabellen:
  users                – Nutzerverwaltung (Epic 1: Auth & Mandantenfähigkeit)
  cases                – Fälle (Epic 1 & 5: Schaltzentrale)
  documents            – Dokumente (Epic 2: Ingestion & S3)
  chronology_events    – Zeitleiste (Epic 4: Der Rote Faden)
  mobile_upload_tokens – QR-Code-Upload-Token (Epic 2 US-2.3)
  password_reset_tokens – Passwort-Reset-Token (Epic 1)
  llama_parse_usage    – Free-Tier-Monitoring für LlamaParse (Epic 8 US-8.3)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# 1. USERS
# ─────────────────────────────────────────────────────────────────────────────


class User(Base):
    """
    Nutzer-Modell für Auth & Mandantenfähigkeit (Epic 1).

    Attributes:
        id: Primärschlüssel (UUID).
        email: Eindeutige E-Mail-Adresse.
        hashed_password: bcrypt-Hash des Passworts.
        accepted_terms: Zustimmung zu AGB.
        created_at: Erstellungszeitpunkt.
        first_name: Vorname (nullable – Rückwärtskompatibilität).
        last_name: Nachname (nullable).
        street: Straße und Hausnummer (nullable).
        postal_code: PLZ, 5 Ziffern (nullable).
        city: Stadt (nullable).
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Profil-Daten (US-7.3) – nullable für Rückwärtskompatibilität
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    street: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    cases: Mapped[List["Case"]] = relationship(
        "Case", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id!s:.8}, email={self.email!r})>"

    def to_dict(self) -> Dict[str, Any]:
        """Serialisiert den Nutzer für API-Responses (ohne Passwort-Hash)."""
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


# ─────────────────────────────────────────────────────────────────────────────
# 2. CASES
# ─────────────────────────────────────────────────────────────────────────────


class Case(Base):
    """
    Fall-Modell als zentrale Schaltzentrale (Epic 1 & 5).

    Status-Flow: DRAFT → WAITING_FOR_USER → PAID → COMPLETED

    Attributes:
        id: Primärschlüssel (UUID).
        user_id: Fremdschlüssel auf User (Mandantenfähigkeit).
        status: Aktueller Fall-Status.
        stripe_session_id: Stripe-Checkout-Session (Epic 5).
        extracted_data: KI-extrahierte Fakten als JSONB.
        created_at: Erstellungszeitpunkt.
        updated_at: Letzter Änderungszeitpunkt.
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship("User", back_populates="cases")
    documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="case", cascade="all, delete-orphan"
    )
    timeline_events: Mapped[List["ChronologyEvent"]] = relationship(
        "ChronologyEvent", back_populates="case", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Case(id={self.id!s:.8}, status={self.status!r}, user_id={self.user_id!s:.8})>"

    def to_dict(self) -> Dict[str, Any]:
        """Serialisiert den Fall für API-Responses."""
        return {
            "case_id": str(self.id),
            "user_id": str(self.user_id),
            "status": self.status,
            "extracted_data": self.extracted_data,
            "document_count": len(self.documents),
            "network_operator": (self.extracted_data or {}).get("network_operator"),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# 3. DOCUMENTS
# ─────────────────────────────────────────────────────────────────────────────


class Document(Base):
    """
    Dokument-Modell für Ingestion & S3-Storage (Epic 2).

    Attributes:
        id: Primärschlüssel (UUID).
        case_id: Fremdschlüssel auf Case.
        filename: Originaler Dateiname.
        s3_key: Pfad im MinIO/S3-Bucket ({case_id}/{uuid}.{ext}).
        document_type: Klassifizierung (INVOICE, CONTRACT, etc.).
        ocr_status: Verarbeitungsstatus (pending|parsing|llama_parse_fallback|masking|completed|error).
        masked_text: PII-maskierter Klartext nach Extraktion (US-2.5, Epic 8).
        created_at: Upload-Zeitpunkt.
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    case: Mapped["Case"] = relationship("Case", back_populates="documents")

    def __repr__(self) -> str:
        return (
            f"<Document(id={self.id!s:.8}, filename={self.filename!r}, "
            f"ocr_status={self.ocr_status!r})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialisiert das Dokument für API-Responses."""
        return {
            "document_id": str(self.id),
            "case_id": str(self.case_id),
            "filename": self.filename,
            "s3_key": self.s3_key,
            "document_type": self.document_type,
            "ocr_status": self.ocr_status,
            "created_at": self.created_at.isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# 4. CHRONOLOGY_EVENTS
# ─────────────────────────────────────────────────────────────────────────────


class ChronologyEvent(Base):
    """
    Zeitleisten-Ereignis (Epic 4: Der Rote Faden).

    Attributes:
        id: Primärschlüssel (UUID).
        case_id: Fremdschlüssel auf Case.
        event_date: Datum des Ereignisses.
        description: Beschreibung des Ereignisses.
        source_doc_id: Optionaler Verweis auf Quelldokument.
        source_type: 'ai' oder 'user' (verhindert Überschreiben von User-Daten).
        is_gap: Kennzeichnung fehlender Belege (Soft-Blocker).
    """

    __tablename__ = "chronology_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_doc_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(20), default="ai")
    is_gap: Mapped[bool] = mapped_column(Boolean, default=False)

    case: Mapped["Case"] = relationship("Case", back_populates="timeline_events")

    def __repr__(self) -> str:
        return (
            f"<ChronologyEvent(id={self.id!s:.8}, date={self.event_date}, "
            f"is_gap={self.is_gap})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialisiert das Ereignis für API-Responses."""
        return {
            "event_id": str(self.id),
            "case_id": str(self.case_id),
            "event_date": self.event_date.isoformat(),
            "description": self.description,
            "source_doc_id": str(self.source_doc_id) if self.source_doc_id else None,
            "source_type": self.source_type,
            "is_gap": self.is_gap,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 5. MOBILE_UPLOAD_TOKENS
# ─────────────────────────────────────────────────────────────────────────────


class MobileUploadToken(Base):
    """
    QR-Code-Upload-Token (Epic 2 US-2.3).

    Der Raw-Token wird niemals in der DB gespeichert – nur der SHA-256-Hash.

    Attributes:
        id: Primärschlüssel (UUID).
        case_id: Fremdschlüssel auf Case.
        token_hash: SHA-256-Hash des Raw-Tokens.
        expires_at: Ablaufzeitpunkt (15 Minuten nach Erstellung).
        used: Einmaligkeitsschutz.
        created_at: Erstellungszeitpunkt.
    """

    __tablename__ = "mobile_upload_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<MobileUploadToken(id={self.id!s:.8}, used={self.used}, expires_at={self.expires_at})>"


# ─────────────────────────────────────────────────────────────────────────────
# 7. LLAMA_PARSE_USAGE
# ─────────────────────────────────────────────────────────────────────────────


class LlamaParseUsage(Base):
    """
    Free-Tier-Monitoring für LlamaParse API (Epic 8 US-8.3).

    Logt den täglichen Seitenverbrauch um das kostenlose Tageslimit
    von 1.000 Seiten im Blick zu behalten.

    Attributes:
        id: Auto-Increment-Primärschlüssel.
        date: Datum des Eintrags (eindeutig, ein Eintrag pro Tag).
        pages_used: Anzahl der an LlamaParse gesendeten Seiten.
    """

    __tablename__ = "llama_parse_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    pages_used: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<LlamaParseUsage(date={self.date}, pages_used={self.pages_used})>"

    def to_dict(self) -> Dict[str, Any]:
        """Serialisiert den Nutzungseintrag für API-Responses."""
        return {
            "date": self.date.isoformat(),
            "pages_used": self.pages_used,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 8. PASSWORD_RESET_TOKENS
# ─────────────────────────────────────────────────────────────────────────────


class PasswordResetToken(Base):
    """
    Passwort-Reset-Token (Epic 1).

    Der Raw-Token wird niemals in der DB gespeichert – nur der SHA-256-Hash.

    Attributes:
        id: Primärschlüssel (UUID).
        user_id: Fremdschlüssel auf User.
        token_hash: SHA-256-Hash des Raw-Tokens.
        expires_at: Ablaufzeitpunkt.
        used: Einmaligkeitsschutz.
        created_at: Erstellungszeitpunkt.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<PasswordResetToken(id={self.id!s:.8}, used={self.used}, expires_at={self.expires_at})>"
