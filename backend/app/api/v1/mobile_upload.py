"""
Mobile Upload Router – Epic 2 (US-2.3): QR-Code Magic Flow.

Endpunkte:
  POST /upload-tokens              – Kurzlebiges Upload-Token für QR-Code generieren
  POST /mobile-upload              – Datei-Upload vom Smartphone (Token-Auth)
  GET  /upload-tokens/{token}/info – Token-Status prüfen (für Mobile-Page)

Flow:
  1. PC fragt POST /upload-tokens an → erhält token + QR-Code-URL
  2. QR-Code-URL öffnet Mobile-Seite mit einmaligem Token
  3. Smartphone lädt Foto via POST /mobile-upload (token im Body)
  4. PC pollt GET /cases/{case_id}/documents alle 2 Sekunden auf neue Dateien
"""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.domain.models.db import Case, Document, MobileUploadToken
from app.infrastructure.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mobile-upload"])

TOKEN_TTL_MINUTES = 15
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Magic-Bytes-Validierung (gleich wie in documents.py)
_MAGIC: list[tuple[bytes, str, str]] = [
    (b"\x25\x50\x44\x46", "application/pdf", "pdf"),
    (b"\xFF\xD8\xFF",     "image/jpeg",      "jpg"),
    (b"\x89\x50\x4E\x47", "image/png",       "png"),
]


def _detect_mime(header: bytes) -> tuple[str, str] | None:
    for magic, mime, ext in _MAGIC:
        if header[: len(magic)] == magic:
            return mime, ext
    return None


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ── POST /upload-tokens ───────────────────────────────────────────────────────

class CreateTokenRequest(BaseModel):
    case_id: str


@router.post("/upload-tokens", status_code=201)
def create_upload_token(
    body:         CreateTokenRequest,
    current_user: CurrentUser,
    db:           Session = Depends(get_db),
):
    """
    Generiert ein kurzlebiges Upload-Token (15 Minuten) für den QR-Code-Flow.

    Nur der Eigentümer des Falls kann ein Token erzeugen.
    Gibt den raw token zurück – dieser wird NIE in der DB gespeichert (nur SHA-256).
    """
    try:
        case_uuid = uuid.UUID(body.case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Fall nicht gefunden.")

    case = (
        db.query(Case)
        .filter(Case.id == case_uuid, Case.user_id == current_user.id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Fall nicht gefunden.")

    raw_token  = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MINUTES)

    db_token = MobileUploadToken(
        case_id    = case.id,
        token_hash = token_hash,
        expires_at = expires_at,
    )
    db.add(db_token)
    db.commit()

    logger.info("Mobile-Upload-Token erstellt für Fall %s (läuft ab: %s)", body.case_id, expires_at)
    return {
        "token":      raw_token,
        "expires_at": expires_at.isoformat(),
        "upload_url": f"/mobile-upload?token={raw_token}",
    }


# ── POST /mobile-upload ───────────────────────────────────────────────────────

@router.post("/mobile-upload", status_code=201)
async def mobile_upload(
    background_tasks: BackgroundTasks,
    db:               Session = Depends(get_db),
    file:             UploadFile = File(...),
    token:            str = Query(..., description="Einmaliges Upload-Token aus dem QR-Code"),
):
    """
    Nimmt einen Datei-Upload vom Smartphone entgegen (Token-Auth, kein Cookie nötig).

    - Token wird verifiziert (Existenz, Ablauf, Einmalnutzung)
    - Token wird nach Nutzung als `used=True` markiert (Einmalnutzung)
    - Datei wird in S3 gespeichert und OCR gestartet
    """
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)

    db_token = (
        db.query(MobileUploadToken)
        .filter(MobileUploadToken.token_hash == token_hash)
        .first()
    )

    if not db_token:
        raise HTTPException(status_code=401, detail="Ungültiges Upload-Token.")

    # Ablauf prüfen (expires_at ist naive datetime in DB → timezone-aware machen)
    expires_at = db_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        raise HTTPException(status_code=401, detail="Upload-Token abgelaufen.")

    if db_token.used:
        raise HTTPException(status_code=401, detail="Upload-Token wurde bereits verwendet.")

    # Datei einlesen und validieren
    raw = await file.read()

    if len(raw) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Datei zu groß. Maximal 10 MB.")

    mime_result = _detect_mime(raw[:8])
    if mime_result is None:
        raise HTTPException(status_code=415, detail="Nicht unterstütztes Format. Erlaubt: PDF, JPEG, PNG.")

    _mime_type, ext = mime_result

    # In S3 speichern
    doc_id = uuid.uuid4()
    s3_key = f"{db_token.case_id}/{doc_id}.{ext}"
    filename = file.filename or f"{doc_id}.{ext}"

    from app.infrastructure.storage import get_storage
    try:
        get_storage().upload_file(data=raw, key=s3_key, content_type=_mime_type)
    except Exception as exc:
        logger.error("Mobile-Upload S3-Fehler: %s", exc)
        raise HTTPException(status_code=500, detail="Datei konnte nicht gespeichert werden.")

    # DB-Eintrag anlegen
    document = Document(
        id            = doc_id,
        case_id       = db_token.case_id,
        filename      = filename,
        s3_key        = s3_key,
        document_type = "UNKNOWN",
    )
    db.add(document)

    # Token als verbraucht markieren
    db_token.used = True
    db.commit()
    db.refresh(document)

    # OCR asynchron starten
    from app.workers.ocr_worker import run_ocr
    background_tasks.add_task(run_ocr, str(doc_id))

    logger.info("Mobile-Upload: %s für Fall %s", doc_id, db_token.case_id)
    return {
        "document_id": str(document.id),
        "filename":    document.filename,
        "ocr_status":  document.ocr_status,
        "status":      "stored",
    }


# ── GET /upload-tokens/{token}/info ───────────────────────────────────────────

@router.get("/upload-tokens/{token}/info")
def get_token_info(token: str, db: Session = Depends(get_db)):
    """
    Prüft ob ein Token noch gültig ist (für die Mobile-Seite beim Laden).
    Gibt case_id zurück, damit die Mobile-Seite den Kontext kennt.
    """
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)

    db_token = (
        db.query(MobileUploadToken)
        .filter(MobileUploadToken.token_hash == token_hash)
        .first()
    )

    if not db_token:
        raise HTTPException(status_code=404, detail="Token nicht gefunden.")

    expires_at = db_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at or db_token.used:
        raise HTTPException(status_code=410, detail="Token abgelaufen oder bereits verwendet.")

    return {
        "case_id":    str(db_token.case_id),
        "expires_at": expires_at.isoformat(),
        "valid":      True,
    }
