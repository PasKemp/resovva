"""
Documents Router – Epic 2 (US-2.2): Datei-Upload & MIME-Validierung.

Endpunkte:
  POST   /cases/{case_id}/documents                    – Datei hochladen
  GET    /cases/{case_id}/documents                    – Alle Dokumente abrufen
  DELETE /cases/{case_id}/documents/{document_id}      – Dokument löschen

Sicherheit:
  - Auth erforderlich (CurrentUser)
  - Case-Eigentümerschaft geprüft (Fremde case_id → 404)
  - MIME-Typ via Magic-Bytes geprüft (kein Extension-Spoofing möglich)
  - 10 MB Größenlimit erzwungen
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.domain.models.db import Case, Document
from app.infrastructure.database import get_db
from app.infrastructure.storage import get_storage
from app.workers.ocr_worker import run_ocr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["documents"])

# ── Konstanten ────────────────────────────────────────────────────────────────

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Magic-Bytes → (MIME-Type, Dateiendung)
_MAGIC: list[tuple[bytes, str, str]] = [
    (b"\x25\x50\x44\x46", "application/pdf", "pdf"),  # %PDF
    (b"\xFF\xD8\xFF",     "image/jpeg",      "jpg"),  # JPEG SOI
    (b"\x89\x50\x4E\x47", "image/png",       "png"),  # PNG signature
]


# ── Response Schemas ──────────────────────────────────────────────────────────


class DocumentEntry(BaseModel):
    """Einzelnes Dokument in der Übersichtsliste."""

    document_id: str
    filename: str
    document_type: str
    ocr_status: str
    created_at: str


class DocumentListResponse(BaseModel):
    """Response für GET /cases/{case_id}/documents."""

    documents: List[DocumentEntry]


class DocumentUploadResponse(BaseModel):
    """Response für POST /cases/{case_id}/documents."""

    document_id: str
    filename: str
    s3_key: str
    ocr_status: str
    status: str


class DocumentDeleteResponse(BaseModel):
    """Response für DELETE /cases/{case_id}/documents/{document_id}."""

    status: str
    message: str


# ── Private Hilfsfunktionen ───────────────────────────────────────────────────


def _detect_mime(header: bytes) -> Optional[tuple[str, str]]:
    """
    Erkennt MIME-Typ anhand der Magic-Bytes einer Datei.

    Args:
        header: Erste 8 Bytes der Datei.

    Returns:
        Tuple (mime_type, extension) oder None wenn unbekanntes Format.
    """
    for magic, mime, ext in _MAGIC:
        if header[: len(magic)] == magic:
            return mime, ext
    return None


def _get_owned_case(case_id: str, current_user, db: Session) -> Case:
    """
    Lädt den Fall und prüft Eigentümerschaft.

    Args:
        case_id: UUID-String des Falls.
        current_user: Authentifizierter Nutzer.
        db: Datenbankverbindung.

    Returns:
        Case: Das geladene Fall-Objekt.

    Raises:
        HTTPException 404: Ungültige UUID, Fall nicht gefunden oder Fremdfall.
    """
    try:
        case_uuid = uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Fall nicht gefunden.")

    case = (
        db.query(Case)
        .filter(Case.id == case_uuid, Case.user_id == current_user.id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Fall nicht gefunden.")

    return case


# ── POST /cases/{case_id}/documents ──────────────────────────────────────────


@router.post("/{case_id}/documents", status_code=201, response_model=DocumentUploadResponse)
async def upload_document(
    case_id: str,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    """
    Lädt ein Dokument in den S3-Bucket hoch und legt einen DB-Eintrag an.

    - MIME-Validierung per Magic-Bytes (kein Extension-Spoofing möglich)
    - 10 MB Größenlimit (nach Browser-Komprimierung)
    - OCR + PII-Masking wird asynchron gestartet (US-2.4)
    - S3-Pfadstruktur: {case_id}/{uuid}.{ext}

    Args:
        case_id: UUID des Ziel-Falls.
        file: Hochzuladende Datei (PDF, JPEG oder PNG).

    Returns:
        DocumentUploadResponse: Metadaten des gespeicherten Dokuments.

    Raises:
        HTTPException 404: Fall nicht gefunden oder Fremdfall.
        HTTPException 413: Datei überschreitet 10 MB Limit.
        HTTPException 415: Nicht unterstütztes Dateiformat.
        HTTPException 500: Storage-Fehler.
    """
    case = _get_owned_case(case_id, current_user, db)

    raw = await file.read()

    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Datei zu groß. Maximale Größe: {MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )

    mime_result = _detect_mime(raw[:8])
    if mime_result is None:
        raise HTTPException(
            status_code=415,
            detail="Nicht unterstütztes Dateiformat. Erlaubt: PDF, JPEG, PNG.",
        )
    mime_type, ext = mime_result

    doc_id = uuid.uuid4()
    s3_key = f"{case.id}/{doc_id}.{ext}"
    filename = file.filename or f"{doc_id}.{ext}"

    storage = get_storage()
    try:
        storage.upload_file(data=raw, key=s3_key, content_type=mime_type)
    except Exception as exc:
        logger.error("Upload-Fehler (case=%s, key=%s): %s", case_id, s3_key, exc)
        raise HTTPException(status_code=500, detail="Datei konnte nicht gespeichert werden.")

    document = Document(
        id=doc_id,
        case_id=case.id,
        filename=filename,
        s3_key=s3_key,
        document_type="UNKNOWN",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(run_ocr, str(doc_id))

    logger.info("Dokument hochgeladen: %s (Fall: %s)", doc_id, case_id)

    return DocumentUploadResponse(
        document_id=str(document.id),
        filename=document.filename,
        s3_key=document.s3_key,
        ocr_status=document.ocr_status,
        status="stored",
    )


# ── GET /cases/{case_id}/documents ───────────────────────────────────────────


@router.get("/{case_id}/documents", response_model=DocumentListResponse)
def list_documents(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    """
    Gibt alle Dokumente eines Falls zurück (für Polling und Anzeige).

    Args:
        case_id: UUID des Falls.

    Returns:
        DocumentListResponse: Liste aller Dokumente mit OCR-Status.
    """
    case = _get_owned_case(case_id, current_user, db)

    return DocumentListResponse(
        documents=[
            DocumentEntry(
                document_id=str(d.id),
                filename=d.filename,
                document_type=d.document_type,
                ocr_status=d.ocr_status,
                created_at=d.created_at.isoformat(),
            )
            for d in case.documents
        ]
    )


# ── DELETE /cases/{case_id}/documents/{document_id} ──────────────────────────


@router.delete(
    "/{case_id}/documents/{document_id}",
    response_model=DocumentDeleteResponse,
)
def delete_document(
    case_id: str,
    document_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> DocumentDeleteResponse:
    """
    Löscht ein einzelnes Dokument aus S3 und der DB.

    Storage-Fehler werden geloggt, unterbrechen aber nicht den DB-Delete.

    Args:
        case_id: UUID des Falls.
        document_id: UUID des zu löschenden Dokuments.

    Returns:
        DocumentDeleteResponse: Bestätigung der Löschung.

    Raises:
        HTTPException 404: Fall oder Dokument nicht gefunden.
    """
    case = _get_owned_case(case_id, current_user, db)

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")

    doc = (
        db.query(Document)
        .filter(Document.id == doc_uuid, Document.case_id == case.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")

    storage = get_storage()
    try:
        storage.delete_file(doc.s3_key)
    except Exception as exc:
        logger.error("Fehler beim Löschen aus Storage (key=%s): %s", doc.s3_key, exc)

    db.delete(doc)
    db.commit()

    logger.info("Dokument gelöscht: %s (Fall: %s)", document_id, case_id)

    return DocumentDeleteResponse(
        status="success",
        message="Dokument gelöscht.",
    )
