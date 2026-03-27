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

from app.api.dependencies import CurrentUser, get_owned_case
from app.domain.models.db import Document
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
    masked_text_preview: Optional[str] = None  # US-9.3: erste 500 Zeichen für Split-View


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


class SummaryResponse(BaseModel):
    """Response für POST /cases/{case_id}/documents/{doc_id}/summarize."""

    summary: Optional[str] = None


# ── Private Hilfsfunktionen ───────────────────────────────────────────────────


def _preview(text: Optional[str], max_chars: int) -> Optional[str]:
    """Kürzt Text auf max_chars, bricht am letzten Leerzeichen ab (kein Mid-Word-Cut)."""
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last_space = cut.rfind(" ")
    return cut[:last_space] if last_space > max_chars // 2 else cut


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
    case = get_owned_case(case_id, current_user, db)

    raw = await file.read()

    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Datei zu groß. Maximale Größe: {MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )

    mime_result = _detect_mime(raw[:8])
    if mime_result is None:
        filename_check = (file.filename or "").lower()
        if filename_check.endswith(".txt"):
            try:
                raw.decode("utf-8")
                mime_type, ext = "text/plain", "txt"
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=415,
                    detail="Textdatei ist kein gültiges UTF-8 Format.",
                )
        else:
            raise HTTPException(
                status_code=415,
                detail="Nicht unterstütztes Dateiformat. Erlaubt: PDF, JPEG, PNG, TXT.",
            )
    else:
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
    case = get_owned_case(case_id, current_user, db)

    return DocumentListResponse(
        documents=[
            DocumentEntry(
                document_id=str(d.id),
                filename=d.filename,
                document_type=d.document_type,
                ocr_status=d.ocr_status,
                created_at=d.created_at.isoformat(),
                masked_text_preview=_preview(d.masked_text, 2500),
            )
            for d in case.documents
        ]
    )


# ── POST /cases/{case_id}/documents/{document_id}/summarize ──────────────────


@router.post(
    "/{case_id}/documents/{document_id}/summarize",
    response_model=SummaryResponse,
)
async def summarize_document(
    case_id: str,
    document_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> SummaryResponse:
    """
    Erstellt eine KI-Zusammenfassung für ein Dokument (gpt-4o-mini).

    Gibt { summary: null } zurück wenn der Text zu kurz ist oder ein Fehler auftritt.
    """
    from app.agents.nodes.extract import _get_mini_llm

    case = get_owned_case(case_id, current_user, db)

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")

    doc = db.query(Document).filter(
        Document.id == doc_uuid,
        Document.case_id == case.id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")

    # Cache-Hit: bereits gespeichert → kein LLM-Aufruf
    if doc.ai_summary:
        return SummaryResponse(summary=doc.ai_summary)

    if not doc.masked_text or len(doc.masked_text) < 300:
        return SummaryResponse(summary=None)

    try:
        llm = _get_mini_llm()
        prompt = (
            "Du analysierst ein deutsches Rechtsdokument. "
            "Erstelle eine prägnante Zusammenfassung in 3–5 Stichpunkten. "
            "Fokus auf: Dokumenttyp, beteiligte Parteien, wichtige Daten und Beträge, Kernaussage. "
            "Antworte auf Deutsch. Jeder Punkt beginnt mit '- '.\n\n"
            f"Dateiname: {doc.filename}\n\n"
            f"Text:\n{doc.masked_text[:3000]}"
        )
        result = await llm.ainvoke(prompt)
        summary_text = result.content.strip()
        doc.ai_summary = summary_text
        db.commit()
        return SummaryResponse(summary=summary_text)
    except Exception:
        logger.warning("summarize_document: LLM-Fehler für Dokument %s.", document_id)
        return SummaryResponse(summary=None)


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
    case = get_owned_case(case_id, current_user, db)

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
