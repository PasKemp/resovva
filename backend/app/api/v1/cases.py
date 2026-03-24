"""
Cases Router – Epic 1 (US-1.6 & US-1.7): Multi-Case Dashboard & DSGVO Hard-Delete.

Endpunkte:
  GET    /cases                    – Alle Fälle des eingeloggten Nutzers (Dashboard)
  POST   /cases                    – Neuen leeren Fall anlegen
  DELETE /cases/{case_id}          – Fall + alle Daten permanent löschen (DSGVO)
  POST   /cases/{case_id}/analyze  – KI-Analyse starten (Epic 3)
  GET    /cases/{case_id}/status   – Verarbeitungsfortschritt abfragen

Mandantenfähigkeit: Alle Queries filtern nach user_id des authentifizierten Nutzers.
Sicherheit: Fremde case_id → 404 (nicht 403), kein Informationsleak.
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser
from app.domain.models.db import Case
from app.infrastructure.database import get_db
from app.infrastructure.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["cases"])


# ── Response Schemas ──────────────────────────────────────────────────────────


class CaseSummary(BaseModel):
    """Einzelner Fall in der Übersichtsliste."""

    case_id: str
    created_at: str
    status: str
    network_operator: Optional[str]
    document_count: int


class CaseListResponse(BaseModel):
    """Response für GET /cases."""

    cases: List[CaseSummary]


class CaseCreateResponse(BaseModel):
    """Response für POST /cases."""

    case_id: str
    status: str
    message: str


class CaseDeleteResponse(BaseModel):
    """Response für DELETE /cases/{case_id}."""

    status: str
    message: str


class CaseAnalyzeResponse(BaseModel):
    """Response für POST /cases/{case_id}/analyze."""

    status: str
    message: str


class CaseStatusResponse(BaseModel):
    """Response für GET /cases/{case_id}/status."""

    status: str
    total: int
    completed: int
    preview: Optional[str] = None


# ── GET /cases ────────────────────────────────────────────────────────────────


@router.get("", response_model=CaseListResponse)
def list_cases(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> CaseListResponse:
    """
    Lädt alle Fälle des eingeloggten Nutzers für das Dashboard.

    Returns:
        CaseListResponse: Liste der Fälle, sortiert nach Erstelldatum (neueste zuerst).
    """
    cases = (
        db.query(Case)
        .filter(Case.user_id == current_user.id)
        .order_by(Case.created_at.desc())
        .all()
    )

    return CaseListResponse(
        cases=[
            CaseSummary(
                case_id=str(c.id),
                created_at=c.created_at.isoformat(),
                status=c.status,
                network_operator=(c.extracted_data or {}).get("network_operator"),
                document_count=len(c.documents),
            )
            for c in cases
        ]
    )


# ── POST /cases ───────────────────────────────────────────────────────────────


@router.post("", status_code=201, response_model=CaseCreateResponse)
def create_case(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> CaseCreateResponse:
    """
    Legt einen neuen, leeren Fall an (Klick auf '+ Neuen Fall starten').

    Returns:
        CaseCreateResponse: ID und Status des neuen Falls.
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

    return CaseCreateResponse(
        case_id=str(case.id),
        status=case.status,
        message="Neuer Fall erfolgreich angelegt.",
    )


# ── DELETE /cases/{case_id} ───────────────────────────────────────────────────


@router.delete("/{case_id}", response_model=CaseDeleteResponse)
def delete_case(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> CaseDeleteResponse:
    """
    Löscht einen Fall und alle zugehörigen Daten permanent (DSGVO Hard-Delete).

    Reihenfolge: Storage → Qdrant → PostgreSQL (von außen nach innen).
    Fremde case_id → 404 (kein Informationsleak über existierende IDs).

    Args:
        case_id: UUID des zu löschenden Falls.

    Returns:
        CaseDeleteResponse: Bestätigung der Löschung.

    Raises:
        HTTPException 404: Fall nicht gefunden oder gehört anderem Nutzer.
    """
    case = _get_owned_case(case_id, current_user, db)

    _delete_from_storage(case)
    _delete_from_qdrant(case_id)

    db.delete(case)
    db.commit()

    logger.info("Fall %s und alle Daten gelöscht (User: %s)", case_id, current_user.id)

    return CaseDeleteResponse(
        status="success",
        message="Fall wurde dauerhaft gelöscht.",
    )


# ── POST /cases/{case_id}/analyze ─────────────────────────────────────────────


@router.post("/{case_id}/analyze", status_code=202, response_model=CaseAnalyzeResponse)
def start_analysis(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> CaseAnalyzeResponse:
    """
    Startet die KI-Analyse des Falls (LangGraph-Agent, Epic 3).

    Voraussetzung: Mindestens ein Dokument vorhanden, alle OCR abgeschlossen.

    Args:
        case_id: UUID des Falls.

    Returns:
        CaseAnalyzeResponse: Bestätigung (202 Accepted – Analyse läuft asynchron).

    Raises:
        HTTPException 422: Keine Dokumente im Fall.
        HTTPException 409: Mindestens ein Dokument noch in Verarbeitung.
        HTTPException 404: Fall nicht gefunden oder gehört anderem Nutzer.
    """
    case = _get_owned_case(case_id, current_user, db)

    docs = case.documents
    if not docs:
        raise HTTPException(status_code=422, detail="Keine Dokumente im Fall.")

    pending = [d for d in docs if d.ocr_status in ("pending", "processing")]
    if pending:
        raise HTTPException(
            status_code=409,
            detail=f"{len(pending)} Dokument(e) noch in Verarbeitung. Bitte warten.",
        )

    # TODO (Epic 3): LangGraph-Agent starten
    logger.info("Analyse gestartet (Stub): Fall %s", case_id)

    return CaseAnalyzeResponse(
        status="accepted",
        message="Analyse wurde gestartet.",
    )


# ── GET /cases/{case_id}/status ───────────────────────────────────────────────


@router.get("/{case_id}/status", response_model=CaseStatusResponse)
def get_case_status(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> CaseStatusResponse:
    """
    Gibt den Verarbeitungsfortschritt aller Dokumente eines Falls zurück.

    Aggregierter Status:
      - "processing": mindestens ein Dokument wird noch verarbeitet
      - "completed":  alle Dokumente abgeschlossen (OCR fertig)
      - "error":      mindestens ein Dokument mit Fehler
      - "empty":      keine Dokumente im Fall

    Args:
        case_id: UUID des Falls.

    Returns:
        CaseStatusResponse: Aggregierter Status mit Zählern und optionalem Preview-Text.
    """
    case = _get_owned_case(case_id, current_user, db)

    docs = case.documents
    if not docs:
        return CaseStatusResponse(status="empty", total=0, completed=0)

    statuses = [d.ocr_status for d in docs]

    if any(s in ("processing", "pending") for s in statuses):
        agg_status = "processing"
    elif any(s == "error" for s in statuses):
        agg_status = "error"
    else:
        agg_status = "completed"

    completed_count = sum(1 for s in statuses if s == "completed")
    preview_doc = next((d for d in docs if d.ocr_status == "completed" and d.masked_text), None)
    preview = preview_doc.masked_text[:500] if preview_doc else None

    return CaseStatusResponse(
        status=agg_status,
        total=len(docs),
        completed=completed_count,
        preview=preview,
    )


# ── Private Hilfsfunktionen ───────────────────────────────────────────────────


def _get_owned_case(case_id: str, current_user, db: Session) -> Case:
    """
    Lädt einen Fall und prüft Eigentümerschaft.

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


def _delete_from_storage(case: Case) -> None:
    """
    Löscht alle Dokument-Dateien des Falls aus MinIO/S3.

    Storage-Fehler werden geloggt, unterbrechen aber nicht den Löschvorgang
    (DB-Cleanup hat Vorrang).
    """
    storage = get_storage()
    for document in case.documents:
        try:
            storage.delete_file(document.s3_key)
        except Exception as exc:
            logger.error(
                "Fehler beim Löschen aus Storage (key=%s): %s",
                document.s3_key,
                exc,
            )


def _delete_from_qdrant(case_id: str) -> None:
    """
    Löscht Vektor-Embeddings des Falls aus Qdrant.

    TODO (Epic 2/3): Qdrant-Client aktivieren und Punkte löschen.
    """
    try:
        logger.debug("Qdrant-Delete (Stub) für Case: %s", case_id)
    except Exception as exc:
        logger.error("Fehler beim Löschen aus Qdrant (Case %s): %s", case_id, exc)
