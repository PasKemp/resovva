"""
Dossier Router.

Handles status polling for generated dossiers and provides secure, time-limited
download links via S3 presigned URLs.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, get_owned_case
from app.api.v1.schemas.dossier import DossierStatusResponse
from app.infrastructure.database import get_db
from app.infrastructure.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["dossier"])

# Configuration: Presigned URL validity duration (US-6.5 requirement)
PRESIGNED_EXPIRES_IN = 300  # 5 minutes in seconds


# ── Dossier Status and Delivery Endpoints ────────────────────────────────────

@router.get("/{case_id}/dossier/status", response_model=DossierStatusResponse)
def get_dossier_status(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> DossierStatusResponse:
    """
    Get the current generation status of a dossier.

    Pollable endpoint that returns the generation state and eventually a
    temporary download link.

    Args:
        case_id: UUID of the case.
        current_user: The authenticated User.
        db: Database session.

    Returns:
        DossierStatusResponse: Current workflow state and optional download link.

    Raises:
        HTTPException:
            403: If payment has not been verified yet.
            404: If case is not found.
    """
    case = get_owned_case(case_id, current_user, db)

    # Permission check: requires payment verification
    allowed_statuses = ("PAID", "GENERATING_DOSSIER", "COMPLETED", "ERROR_GENERATION")
    if case.status not in allowed_statuses:
        logger.warning(
            "Access to dossier status denied: payment missing",
            extra={"case_id": case_id, "status": case.status}
        )
        raise HTTPException(
            status_code=403,
            detail="Dossier restricted - payment pending."
        )

    data = case.extracted_data or {}
    download_url_val: Optional[str] = None

    # Generate presigned URL if generation is complete
    if case.status == "COMPLETED":
        s3_key = data.get("dossier_s3_key")
        if s3_key:
            try:
                storage = get_storage()
                download_url_val = storage.generate_presigned_url(
                    key=s3_key,
                    expires_in=PRESIGNED_EXPIRES_IN
                )
            except Exception as exc:
                logger.error(
                    "Failed to generate presigned URL for status response",
                    extra={"case_id": case_id, "error": str(exc)},
                    exc_info=True
                )

    error_message_val: Optional[str] = None
    if case.status == "ERROR_GENERATION":
        error_log = data.get("error_log", {})
        error_message_val = error_log.get(
            "message", "An unexpected error occurred during dossier generation."
        )

    return DossierStatusResponse(
        status=case.status,
        download_url=download_url_val,
        error_message=error_message_val,
    )


@router.get("/{case_id}/dossier/download")
def download_dossier(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """
    Securely redirect browser to the dossier file in S3.

    Uses a 302-Redirect to a 5-minute presigned URL to prevent URL sharing
    and client-side caching of the actual file location.

    Args:
        case_id: UUID of the case.

    Returns:
        RedirectResponse: Directs browser to S3 download.

    Raises:
        HTTPException:
            404: If dossier is not yet completed or file is missing in metadata.
    """
    case = get_owned_case(case_id, current_user, db)

    if case.status != "COMPLETED":
        raise HTTPException(
            status_code=404,
            detail="Dossier generation not yet completed."
        )

    data = case.extracted_data or {}
    s3_key = data.get("dossier_s3_key")

    if not s3_key:
        logger.error(
            "Dossier marked as COMPLETED but S3 key is missing in metadata",
            extra={"case_id": case_id}
        )
        raise HTTPException(
            status_code=404,
            detail="Dossier file not found."
        )

    try:
        storage = get_storage()
        presigned_url = storage.generate_presigned_url(
            key=s3_key,
            expires_in=PRESIGNED_EXPIRES_IN
        )
    except Exception as exc:
        logger.error(
            "Failed to prepare presigned download URL",
            extra={"case_id": case_id, "error": str(exc)},
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Download could not be prepared. Please try again."
        )

    logger.info(
        "Secure dossier download link generated",
        extra={"case_id": case_id, "user_id": str(current_user.id)}
    )
    return RedirectResponse(url=presigned_url, status_code=302)
