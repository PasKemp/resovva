"""
Dossier Router – Epic 6 (US-6.4 / US-6.5).

Endpunkte:
  GET  /cases/{case_id}/dossier/status   – Status-Polling + Download-URL (Presigned, 5 min)
  GET  /cases/{case_id}/dossier/download – 302-Redirect zur Presigned S3 URL

Status-Werte für das Frontend:
  GENERATING_DOSSIER  – Dossier wird gerade erstellt (Ladeanimation)
  COMPLETED           – Fertig, download_url enthalten
  ERROR_GENERATION    – Fehler beim Erstellen
  PAID                – Zahlung OK, Generation noch nicht gestartet (Edge-Case)
  *                   – Alles andere → noch nicht freigeschaltet (403)

Sicherheit:
  - Alle Endpunkte prüfen Eigentümerschaft (Tenant-Check via get_owned_case)
  - Download generiert eine 5-Minuten-Presigned-URL (kein direkter S3-Link)
  - 302-Redirect statt Rückgabe der URL (verhindert Client-seitiges Caching/Sharing)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, get_owned_case
from app.infrastructure.database import get_db
from app.infrastructure.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["dossier"])

# Presigned-URL-Gültigkeit: 5 Minuten (US-6.5 Anforderung)
PRESIGNED_EXPIRES_IN = 300


# ── Response Schemas ──────────────────────────────────────────────────────────


class DossierStatusResponse(BaseModel):
    """Response für GET /cases/{case_id}/dossier/status."""

    status: str               # GENERATING_DOSSIER | COMPLETED | ERROR_GENERATION | PAID
    download_url: str | None  # Gesetzt wenn COMPLETED (5-Minuten-Presigned-URL)
    error_message: str | None = None


# ── GET /cases/{case_id}/dossier/status ──────────────────────────────────────


@router.get("/{case_id}/dossier/status", response_model=DossierStatusResponse)
def get_dossier_status(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> DossierStatusResponse:
    """
    Gibt den aktuellen Generierungs-Status des Dossiers zurück.

    Das Frontend pollt diesen Endpunkt alle 3 Sekunden.
    Bei COMPLETED ist eine Presigned S3 URL (5 min gültig) in ``download_url`` enthalten.

    Raises:
        HTTPException 404: Fall nicht gefunden / kein Zugriff.
        HTTPException 403: Fall noch nicht bezahlt.
    """
    case = get_owned_case(case_id, current_user, db)

    # Noch nicht freigeschaltet: Zahlung ausstehend
    if case.status not in (
        "PAID", "GENERATING_DOSSIER", "COMPLETED", "ERROR_GENERATION"
    ):
        raise HTTPException(
            status_code=403,
            detail="Dossier noch nicht freigeschaltet – Zahlung ausstehend.",
        )

    data = case.extracted_data or {}
    download_url: str | None = None

    if case.status == "COMPLETED":
        s3_key = data.get("dossier_s3_key")
        if s3_key:
            try:
                storage = get_storage()
                download_url = storage.generate_presigned_url(
                    key=s3_key,
                    expires_in=PRESIGNED_EXPIRES_IN,
                )
            except Exception as exc:
                logger.error(
                    "Dossier-Status: Presigned-URL-Generierung fehlgeschlagen (Case %s): %r",
                    case_id, exc,
                )

    error_message: str | None = None
    if case.status == "ERROR_GENERATION":
        error_log = data.get("error_log", {})
        error_message = error_log.get("message", "Unbekannter Fehler bei der Dossier-Generierung.")

    return DossierStatusResponse(
        status=case.status,
        download_url=download_url,
        error_message=error_message,
    )


# ── GET /cases/{case_id}/dossier/download ─────────────────────────────────────


@router.get("/{case_id}/dossier/download")
def download_dossier(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    Leitet den Browser sicher zum Dossier-Download weiter (302-Redirect).

    Generiert eine auf 5 Minuten befristete Presigned S3 URL und redirectet
    den Browser direkt dorthin. Die eigentliche URL wird nie an den Client
    zurückgegeben (verhindert URL-Sharing und Browser-Caching-Angriffe).

    Raises:
        HTTPException 404: Fall nicht gefunden / nicht bezahlt / kein Dossier.
    """
    case = get_owned_case(case_id, current_user, db)

    if case.status != "COMPLETED":
        raise HTTPException(
            status_code=404,
            detail="Dossier noch nicht fertiggestellt.",
        )

    data = case.extracted_data or {}
    s3_key = data.get("dossier_s3_key")

    if not s3_key:
        logger.error("Dossier-Download: dossier_s3_key fehlt in extracted_data (Case %s).", case_id)
        raise HTTPException(
            status_code=404,
            detail="Dossier-Datei nicht gefunden.",
        )

    try:
        storage = get_storage()
        presigned_url = storage.generate_presigned_url(
            key=s3_key,
            expires_in=PRESIGNED_EXPIRES_IN,
        )
    except Exception as exc:
        logger.error(
            "Dossier-Download: Presigned-URL-Generierung fehlgeschlagen (Case %s): %r",
            case_id, exc,
        )
        raise HTTPException(
            status_code=500,
            detail="Download konnte nicht vorbereitet werden. Bitte erneut versuchen.",
        )

    logger.info("Dossier-Download: Redirect für Case %s (User %s).", case_id, current_user.id)
    return RedirectResponse(url=presigned_url, status_code=302)
