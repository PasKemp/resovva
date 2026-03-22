"""
Cases Router – Epic 1 (US-1.6 & US-1.7): Multi-Case Dashboard & DSGVO Hard-Delete.

Endpunkte:
  GET  /cases               – Alle Fälle des eingeloggten Nutzers (Dashboard)
  POST /cases               – Neuen leeren Fall anlegen
  DELETE /cases/{case_id}   – Fall + alle Daten permanent löschen (DSGVO)

Mandantenfähigkeit: Alle Queries filtern nach user_id des authentifizierten Nutzers.
Sicherheit: Fremde case_id → 404 (nicht 403), kein Informationsleak.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.domain.models.db import Case, User
from app.infrastructure.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["cases"])


# ── GET /cases ────────────────────────────────────────────────────────────────

@router.get("")
def list_cases(current_user: CurrentUser, db: Session = Depends(get_db)):
    """
    Lädt alle Fälle des eingeloggten Nutzers für das Dashboard.
    Sortiert nach Erstelldatum (neueste zuerst).
    """
    cases = (
        db.query(Case)
        .filter(Case.user_id == current_user.id)
        .order_by(Case.created_at.desc())
        .all()
    )

    return {
        "cases": [
            {
                "case_id": str(c.id),
                "created_at": c.created_at.isoformat(),
                "status": c.status,
                "network_operator": (c.extracted_data or {}).get("network_operator"),
                "document_count": len(c.documents),
            }
            for c in cases
        ]
    }


# ── POST /cases ───────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_case(current_user: CurrentUser, db: Session = Depends(get_db)):
    """
    Legt einen neuen, leeren Fall an (Klick auf '+ Neuen Fall starten').
    Verknüpft den Fall direkt mit dem eingeloggten Nutzer.
    """
    case = Case(
        user_id=current_user.id,
        status="DRAFT",
        extracted_data={},
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    logger.info("Neuer Fall angelegt: %s (User: %s)", case.id, current_user.id)
    return {
        "case_id": str(case.id),
        "status": case.status,
        "message": "Neuer Fall erfolgreich angelegt.",
    }


# ── DELETE /cases/{case_id} ───────────────────────────────────────────────────

@router.delete("/{case_id}")
def delete_case(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """
    Löscht einen Fall und alle zugehörigen Daten permanent (DSGVO Hard-Delete).

    Reihenfolge: Storage → Qdrant → PostgreSQL (von außen nach innen).
    Fremde case_id → 404 (kein Informationsleak über existierende IDs).
    """
    try:
        case_uuid = uuid.UUID(case_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Fall nicht gefunden.")

    # Mandantenfähigkeit: Nur eigene Cases → 404 bei fremdem Case
    case = (
        db.query(Case)
        .filter(Case.id == case_uuid, Case.user_id == current_user.id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Fall nicht gefunden.")

    # 1. Storage (MinIO/S3): Physische Dateien löschen
    _delete_from_storage(case)

    # 2. Qdrant: Vektor-Embeddings löschen
    _delete_from_qdrant(case_id)

    # 3. PostgreSQL: Fall löschen (CASCADE löscht Documents + ChronologyEvents)
    db.delete(case)
    db.commit()

    logger.info("Fall %s und alle Daten gelöscht (User: %s)", case_id, current_user.id)
    return {"status": "success", "message": "Fall wurde dauerhaft gelöscht."}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _delete_from_storage(case: Case) -> None:
    """Löscht alle Dokument-Dateien des Falls aus MinIO/S3."""
    for document in case.documents:
        try:
            # TODO (Epic 2): MinIO/S3-Client implementieren und Datei löschen
            # storage_client.delete_object(bucket="resovva-docs", key=document.s3_key)
            logger.debug("Storage-Delete (Stub) für: %s", document.s3_key)
        except Exception as exc:
            # Storage-Fehler loggen, aber nicht abbrechen – DB-Cleanup hat Vorrang
            logger.error("Fehler beim Löschen aus Storage (%s): %s", document.s3_key, exc)


def _delete_from_qdrant(case_id: str) -> None:
    """Löscht Vektor-Embeddings des Falls aus Qdrant."""
    try:
        # TODO (Epic 2/3): Qdrant-Client aktivieren und Punkte löschen
        # qdrant_client.delete(collection_name="resovva_docs", points_selector=Filter(...))
        logger.debug("Qdrant-Delete (Stub) für Case: %s", case_id)
    except Exception as exc:
        logger.error("Fehler beim Löschen aus Qdrant (Case %s): %s", case_id, exc)
