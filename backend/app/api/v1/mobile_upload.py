"""
Mobile Upload Router.

Enables secure file uploads from smartphones via QR-Code tokens.
Implements one-time use tokens and short-lived expiration for secure
cross-device transfers.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
)
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.api.v1.schemas.mobile_upload import (
    CreateTokenRequest,
    MobileUploadResponse,
    TokenInfoResponse,
    TokenResponse,
)
from app.domain.models.db import Case, Document, MobileUploadToken
from app.infrastructure.database import get_db
from app.infrastructure.storage import get_storage
from app.workers.ocr_worker import run_ocr

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mobile-upload"])

# Configuration
TOKEN_TTL_MINUTES: int = 15
MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB limit

# Magic Bytes for mobile upload validation
_MAGIC_FORMATS: list[tuple[bytes, str, str]] = [
    (b"\x25\x50\x44\x46", "application/pdf", "pdf"),
    (b"\xFF\xD8\xFF",     "image/jpeg",      "jpg"),
    (b"\x89\x50\x4E\x47", "image/png",       "png"),
]


# ── Internal Helpers ──────────────────────────────────────────────────────────

def _detect_mime(header: bytes) -> Optional[Tuple[str, str]]:
    """Detect format from magic bytes."""
    for magic, mime, ext in _MAGIC_FORMATS:
        if header.startswith(magic):
            return mime, ext
    return None


def _hash_token(raw_token: str) -> str:
    """Compute SHA-256 hash of a raw token string."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


# ── Token Integration Endpoints ──────────────────────────────────────────────

@router.post("/upload-tokens", status_code=201, response_model=TokenResponse)
def create_upload_token(
    body: CreateTokenRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Generate a short-lived upload token (15 mins) for the QR code flow.

    Only the owner of the given case can generate tokens.
    Returns the raw token string (which is NOT stored in DB).

    Args:
        body: Request containing target case_id.
        current_user: Authenticated user who owns the case.
        db: Database session.

    Returns:
        TokenResponse: Raw token and expiry metadata.

    Raises:
        HTTPException: If case is not found or not owned by user (404).
    """
    try:
        case_uuid = uuid.UUID(body.case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Case not found.")

    case = (
        db.query(Case)
        .filter(Case.id == case_uuid, Case.user_id == current_user.id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_TTL_MINUTES)

    db_token = MobileUploadToken(
        case_id=case.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(db_token)
    db.commit()

    logger.info(
        "Mobile upload token issued",
        extra={"case_id": body.case_id, "expires_at": expires_at.isoformat()}
    )
    
    return TokenResponse(
        token=raw_token,
        expires_at=expires_at.isoformat(),
        upload_url=f"/mobile-upload?token={raw_token}",
    )


@router.get("/upload-tokens/{token}/info", response_model=TokenInfoResponse)
def get_token_info(
    token: str,
    db: Session = Depends(get_db)
) -> TokenInfoResponse:
    """
    Verify if a token is still valid.

    Used by the mobile landing page to retrieve case context and
    check if the upload link is still active.
    """
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)

    db_token = (
        db.query(MobileUploadToken)
        .filter(MobileUploadToken.token_hash == token_hash)
        .first()
    )

    if not db_token:
        raise HTTPException(status_code=404, detail="Token not found.")

    expires_at = db_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at or db_token.used:
        raise HTTPException(status_code=410, detail="Token expired or already used.")

    return TokenInfoResponse(
        case_id=str(db_token.case_id),
        expires_at=expires_at.isoformat(),
        valid=True,
    )


# ── Mobile Upload Endpoint ───────────────────────────────────────────────────

@router.post("/mobile-upload", status_code=201, response_model=MobileUploadResponse)
async def mobile_upload(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    token: str = Query(..., description="The temporary raw token from QR code"),
) -> MobileUploadResponse:
    """
    Receive a file upload from a mobile device (Token auth).

    Validates token validity and single-use status before processing.
    Triggers the asynchronous OCR pipeline on success.

    Args:
        token: Raw token provided in the URL query.
        file: Uploaded image or PDF.

    Returns:
        MobileUploadResponse: Registration metadata.

    Raises:
        HTTPException:
            401: Token invalid, expired, or used.
            413: File exceeds size limit.
            415: Unsupported format.
    """
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)

    db_token = (
        db.query(MobileUploadToken)
        .filter(MobileUploadToken.token_hash == token_hash)
        .first()
    )

    if not db_token:
        raise HTTPException(status_code=401, detail="Invalid upload token.")

    # Timezone awareness fix
    expires_at = db_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        raise HTTPException(status_code=401, detail="Upload token expired.")

    if db_token.used:
        raise HTTPException(status_code=401, detail="Token already consumed.")

    # File Validation
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB).")

    mime_result = _detect_mime(content[:8])
    if not mime_result:
        raise HTTPException(status_code=415, detail="Unsupported format (PDF/JPEG/PNG).")

    mime_type, extension = mime_result

    # Storage Persistence
    doc_id = uuid.uuid4()
    s3_key = f"{db_token.case_id}/{doc_id}.{extension}"
    filename = file.filename or f"mobile_upload_{doc_id}.{extension}"

    try:
        get_storage().upload_file(data=content, key=s3_key, content_type=mime_type)
    except Exception as exc:
        logger.error(
            "S3 mobile upload storage failed",
            extra={"case_id": str(db_token.case_id), "error": str(exc)},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to store document.")

    # DB Registration and Token Consumption
    document = Document(
        id=doc_id,
        case_id=db_token.case_id,
        filename=filename,
        s3_key=s3_key,
        document_type="UNKNOWN",
    )
    db.add(document)
    db_token.used = True
    db.commit()
    db.refresh(document)

    # Async Pipeline Trigger
    background_tasks.add_task(run_ocr, str(doc_id))

    logger.info(
        "Mobile upload successful",
        extra={"case_id": str(db_token.case_id), "document_id": str(doc_id)}
    )
    
    return MobileUploadResponse(
        document_id=str(document.id),
        filename=document.filename,
        ocr_status=document.ocr_status,
        status="stored",
    )
