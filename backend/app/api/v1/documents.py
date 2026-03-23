"""
Documents Router – Epic 2 (US-2.2): Datei-Upload & MIME-Validierung.

Endpunkte:
  POST /cases/{case_id}/documents   – Datei hochladen (PDF, JPEG, PNG)
  GET  /cases/{case_id}/documents   – Alle Dokumente eines Falls abrufen

Sicherheit:
  - Auth erforderlich (CurrentUser)
  - Case-Eigentümerschaft geprüft (Fremde case_id → 404)
  - MIME-Typ via Magic-Bytes geprüft (nicht nur Dateiendung)
  - 10 MB Größenlimit erzwungen
"""

import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.domain.models.db import Case, Document
from app.infrastructure.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["documents"])

# ── Konstanten ────────────────────────────────────────────────────────────────

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Magic-Bytes → (MIME-Type, Dateiendung)
_MAGIC: list[tuple[bytes, str, str]] = [
    (b"\x25\x50\x44\x46", "application/pdf", "pdf"),   # %PDF
    (b"\xFF\xD8\xFF",     "image/jpeg",      "jpg"),   # JPEG SOI
    (b"\x89\x50\x4E\x47", "image/png",       "png"),   # PNG signature
]


def _detect_mime(header: bytes) -> tuple[str, str] | None:
    """Gibt (mime_type, extension) anhand der ersten Bytes zurück."""
    for magic, mime, ext in _MAGIC:
        if header[: len(magic)] == magic:
            return mime, ext
    return None


def _get_owned_case(case_id: str, current_user, db: Session) -> Case:
    """Lädt den Fall und prüft Eigentümerschaft – 404 bei Fremdfall oder ungültiger UUID."""
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

@router.post("/{case_id}/documents", status_code=201)
async def upload_document(
    case_id:      str,
    current_user: CurrentUser,
    db:           Session = Depends(get_db),
    file:         UploadFile = File(...),
):
    """
    Lädt ein Dokument in den S3-Bucket hoch und legt einen DB-Eintrag an.

    - MIME-Validierung per Magic-Bytes (kein Extension-Spoofing möglich)
    - 10 MB Größenlimit (nach Browser-Komprimierung)
    - Pfad im Bucket: {case_id}/{uuid}.{ext}
    """
    case = _get_owned_case(case_id, current_user, db)

    # Datei in den Speicher lesen (Limit + Magic-Bytes-Check)
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
    _mime_type, ext = mime_result

    # Eindeutigen S3-Schlüssel generieren
    doc_id  = uuid.uuid4()
    s3_key  = f"{case.id}/{doc_id}.{ext}"
    filename = file.filename or f"{doc_id}.{ext}"

    # In S3/MinIO hochladen
    from app.infrastructure.storage import get_storage
    storage = get_storage()
    try:
        storage.upload_file(data=raw, key=s3_key, content_type=_mime_type)
    except Exception as exc:
        logger.error("Upload-Fehler (case=%s, key=%s): %s", case_id, s3_key, exc)
        raise HTTPException(status_code=500, detail="Datei konnte nicht gespeichert werden.")

    # DB-Eintrag anlegen
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

    logger.info("Dokument hochgeladen: %s (Fall: %s)", doc_id, case_id)
    return {
        "document_id": str(document.id),
        "filename":    document.filename,
        "s3_key":      document.s3_key,
        "status":      "stored",
    }


# ── GET /cases/{case_id}/documents ───────────────────────────────────────────

@router.get("/{case_id}/documents")
def list_documents(
    case_id:      str,
    current_user: CurrentUser,
    db:           Session = Depends(get_db),
):
    """Gibt alle Dokumente eines Falls zurück (für Polling und Anzeige)."""
    case = _get_owned_case(case_id, current_user, db)

    return {
        "documents": [
            {
                "document_id":    str(d.id),
                "filename":       d.filename,
                "document_type":  d.document_type,
                "created_at":     d.created_at.isoformat(),
            }
            for d in case.documents
        ]
    }


# ── DELETE /cases/{case_id}/documents/{document_id} ──────────────────────────

@router.delete("/{case_id}/documents/{document_id}")
def delete_document(
    case_id:     str,
    document_id: str,
    current_user: CurrentUser,
    db:          Session = Depends(get_db),
):
    """Löscht ein einzelnes Dokument aus S3 und der DB."""
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

    # Aus S3 löschen
    from app.infrastructure.storage import get_storage
    storage = get_storage()
    try:
        storage.delete_file(doc.s3_key)
    except Exception as exc:
        logger.error("Fehler beim Löschen aus Storage (%s): %s", doc.s3_key, exc)

    db.delete(doc)
    db.commit()

    logger.info("Dokument gelöscht: %s (Fall: %s)", document_id, case_id)
    return {"status": "success", "message": "Dokument gelöscht."}
