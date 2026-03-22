import uuid
from datetime import datetime, date
from typing import List, Optional
from sqlalchemy import String, ForeignKey, DateTime, Boolean, Date, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

# -------------------------------------------------------------------
# 1. USERS TABELLE (Epic 1: Auth & Mandantenfähigkeit)
# -------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    accepted_terms: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relation zu Cases (Ein User hat viele Cases)
    cases: Mapped[List["Case"]] = relationship("Case", back_populates="user", cascade="all, delete-orphan")


# -------------------------------------------------------------------
# 2. CASES TABELLE (Epic 1 & 5: Die Schaltzentrale)
# -------------------------------------------------------------------
class Case(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Status-Management (DRAFT, WAITING_FOR_USER, PAID, COMPLETED, etc.)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", index=True)

    # Zahlungstracking (Epic 5)
    stripe_session_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)

    # KI-Extrahierte Fakten (JSONB ist flexibel für Pydantic Models wie "ExtractedEntity")
    # Beinhaltet: malo_id, meter_number, amount_disputed, network_operator
    extracted_data: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationen
    user: Mapped["User"] = relationship("User", back_populates="cases")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="case", cascade="all, delete-orphan")
    timeline_events: Mapped[List["ChronologyEvent"]] = relationship("ChronologyEvent", back_populates="case", cascade="all, delete-orphan")


# -------------------------------------------------------------------
# 3. DOCUMENTS TABELLE (Epic 2: Ingestion & S3)
# -------------------------------------------------------------------
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False) # Pfad im MinIO/S3 Bucket
    document_type: Mapped[str] = mapped_column(String(50), default="UNKNOWN") # INVOICE, CONTRACT, etc.

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationen
    case: Mapped["Case"] = relationship("Case", back_populates="documents")


# -------------------------------------------------------------------
# 4. CHRONOLOGY_EVENTS TABELLE (Epic 4: Der Rote Faden)
# -------------------------------------------------------------------
class ChronologyEvent(Base):
    __tablename__ = "chronology_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)

    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Optionaler Verweis auf das Quelldokument (kann NULL sein bei manuellen Events oder Gaps)
    source_doc_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)

    # 'ai' oder 'user' (wichtig, damit Re-Runs keine User-Daten überschreiben)
    source_type: Mapped[str] = mapped_column(String(20), default="ai")

    # Ist das ein fehlender Beleg? (Der "Soft-Blocker")
    is_gap: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationen
    case: Mapped["Case"] = relationship("Case", back_populates="timeline_events")


# -------------------------------------------------------------------
# 5. PASSWORD_RESET_TOKENS TABELLE (Epic 1: Passwort-Reset-Flow)
# -------------------------------------------------------------------
class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # SHA-256-Hash des Raw-Tokens (niemals Raw-Token in DB speichern)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
