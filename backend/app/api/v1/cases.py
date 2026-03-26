"""
Cases Router – Epic 1–3.

Endpunkte:
  GET    /cases                           – Dashboard-Liste
  POST   /cases                           – Neuen Fall anlegen
  DELETE /cases/{case_id}                 – DSGVO Hard-Delete
  POST   /cases/{case_id}/analyze         – KI-Analyse starten (Epic 3, async)
  GET    /cases/{case_id}/analysis/result – Extraktionsergebnis pollen
  PUT    /cases/{case_id}/analysis/confirm– Daten bestätigen (HiTL, US-3.5)
  GET    /cases/{case_id}/status          – OCR-Verarbeitungsfortschritt

Mandantenfähigkeit: Alle Queries filtern nach user_id.
Sicherheit: Fremde case_id → 404 (kein Informationsleak).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
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


class AnalysisResultResponse(BaseModel):
    """Response für GET /cases/{case_id}/analysis/result."""

    status: str                          # 'analyzing' | 'waiting_for_user' | 'error'
    extracted_data: Optional[dict] = None
    error_message: Optional[str] = None


class ConfirmAnalysisRequest(BaseModel):
    """Request für PUT /cases/{case_id}/analysis/confirm (US-3.5, US-9.4)."""

    meter_number: Optional[str] = None
    malo_id: Optional[str] = None
    dispute_amount: Optional[float] = None
    network_operator: Optional[str] = None
    opponent_category: Optional[str] = None
    opponent_name: Optional[str] = None


class ConfirmAnalysisResponse(BaseModel):
    """Response für PUT /cases/{case_id}/analysis/confirm."""

    status: str
    next_step: str


class CaseStatusResponse(BaseModel):
    """Response für GET /cases/{case_id}/status."""

    status: str
    total: int
    completed: int
    preview: Optional[str] = None


class ExtractionFieldResponse(BaseModel):
    """Einzelnes extrahiertes Feld mit Confidence-Score (US-9.2)."""

    key: str
    value: Optional[Any] = None
    confidence: float = 0.0
    needs_review: bool = True
    auto_accepted: bool = False
    source_document_id: Optional[str] = None
    source_text_snippet: Optional[str] = None
    field_ignored: bool = False


class OpponentResponse(BaseModel):
    """Erkannte Streitpartei (US-9.1)."""

    category: Optional[str] = None
    name: Optional[str] = None
    confidence: float = 0.0
    needs_review: bool = True


class ExtractionResultResponse(BaseModel):
    """Response für GET /cases/{case_id}/extraction-result (US-9.2)."""

    fields: List[ExtractionFieldResponse]
    opponent: OpponentResponse


class UpdateOpponentRequest(BaseModel):
    """Request für PATCH /cases/{case_id} (US-9.4)."""

    opponent_category: Optional[str] = None
    opponent_name: Optional[str] = None


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
async def start_analysis(
    case_id: str,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> CaseAnalyzeResponse:
    """
    Startet die KI-Analyse asynchron als BackgroundTask (Epic 3).

    Voraussetzung: ≥1 Dokument, alle OCR abgeschlossen.
    Nach Abschluss: case.status = WAITING_FOR_USER (pollt Frontend via /analysis/result).

    Raises:
        HTTPException 422: Keine Dokumente.
        HTTPException 409: OCR noch nicht abgeschlossen.
        HTTPException 404: Fall nicht gefunden.
    """
    case = _get_owned_case(case_id, current_user, db)

    docs = case.documents
    if not docs:
        raise HTTPException(status_code=422, detail="Keine Dokumente im Fall.")

    # Alle nicht-abgeschlossenen Zustände (inkl. EPIC8-Status-Flow)
    in_progress = [
        d for d in docs
        if d.ocr_status not in ("completed", "error")
    ]
    if in_progress:
        raise HTTPException(
            status_code=409,
            detail=f"{len(in_progress)} Dokument(e) noch in Verarbeitung. Bitte warten.",
        )

    logger.info("Analyse gestartet: Fall %s", case_id)
    background_tasks.add_task(_run_analysis_background, case_id)

    return CaseAnalyzeResponse(
        status="accepted",
        message="Analyse wurde gestartet.",
    )


async def _run_analysis_background(case_id: str) -> None:
    """Führt den LangGraph-Analyseagenten für einen Fall aus."""
    from langgraph.errors import GraphInterrupt

    from app.agents.graph import get_agent_app

    logger.info("Analyse-Background-Task gestartet (Case %s).", case_id)
    config = {"configurable": {"thread_id": case_id}}
    initial_state: dict = {
        "case_id": case_id,
        "messages": [],
        "documents": [],
        "extracted_entities": {},
        "meter_number": None,
        "malo_id": None,
        "dispute_amount": None,
        "currency": None,
        "network_operator": None,
        "opponent_category": None,
        "opponent_name": None,
        "opponent_confidence": 0.0,
        "field_confidences": {},
        "source_snippets": {},
        "source_doc_ids": {},
        "chronology": [],
        "missing_info": [],
        "dossier_ready": False,
        "payment_status": "pending",
    }
    try:
        agent_app = await get_agent_app()
        await agent_app.ainvoke(initial_state, config=config)
    except GraphInterrupt:
        # Normaler Interrupt – Graph wartet auf Nutzer-Bestätigung (US-3.5).
        # _persist_to_db hat bereits case.status = WAITING_FOR_USER und extracted_at gesetzt.
        logger.info("Analyse Case %s: Graph pausiert vor 'confirm' – wartet auf HiTL-Bestätigung.", case_id)
    except Exception as exc:
        import traceback
        logger.error(
            "Analyse-Background-Task fehlgeschlagen (Case %s): %r\n%s",
            case_id, exc, traceback.format_exc(),
        )
        _set_case_error(case_id)


def _set_case_error(case_id: str) -> None:
    """Setzt case.extracted_data.error bei unbehandeltem Analyse-Fehler."""
    from app.infrastructure.database import get_db_context

    try:
        case_uuid = uuid.UUID(case_id)
    except ValueError:
        return
    with get_db_context() as db:
        case = db.query(Case).filter(Case.id == case_uuid).first()
        if case:
            case.extracted_data = {"error": True}
            db.commit()


# ── GET /cases/{case_id}/analysis/result ──────────────────────────────────────


@router.get("/{case_id}/analysis/result", response_model=AnalysisResultResponse)
def get_analysis_result(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> AnalysisResultResponse:
    """
    Gibt das Ergebnis der KI-Analyse zurück (US-3.2 / US-3.5 Polling).

    Solange die Analyse noch läuft (kein extracted_data) → 404.
    Bei WAITING_FOR_USER → extracted_data ist befüllt, Frontend zeigt Form.

    Raises:
        HTTPException 404: Analyse noch nicht abgeschlossen.
    """
    case = _get_owned_case(case_id, current_user, db)

    data = case.extracted_data or {}
    if not data or ("extracted_at" not in data and "missing_data" not in data and "error" not in data):
        raise HTTPException(status_code=404, detail="Analyse noch nicht abgeschlossen.")

    if data.get("error"):
        return AnalysisResultResponse(
            status="error",
            error_message="Analyse fehlgeschlagen. Bitte erneut starten.",
        )

    return AnalysisResultResponse(
        status="waiting_for_user",
        extracted_data=data,
    )


# ── PUT /cases/{case_id}/analysis/confirm ─────────────────────────────────────


@router.put("/{case_id}/analysis/confirm", response_model=ConfirmAnalysisResponse)
async def confirm_analysis(
    case_id: str,
    payload: ConfirmAnalysisRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> ConfirmAnalysisResponse:
    """
    Bestätigt die extrahierten Daten (Human-in-the-Loop, US-3.5).

    Aktualisiert den LangGraph-State mit den vom Nutzer bestätigten Daten
    und setzt die Graph-Ausführung fort (→ _node_confirm).

    Raises:
        HTTPException 404: Fall nicht gefunden.
        HTTPException 409: Analyse noch nicht bereit für Bestätigung.
    """
    from app.agents.graph import get_agent_app

    case = _get_owned_case(case_id, current_user, db)

    if case.status != "WAITING_FOR_USER":
        raise HTTPException(
            status_code=409,
            detail="Fall ist nicht im Status WAITING_FOR_USER.",
        )

    config = {"configurable": {"thread_id": case_id}}
    confirmed_update = {
        "meter_number": payload.meter_number,
        "malo_id": payload.malo_id,
        "dispute_amount": payload.dispute_amount,
        "network_operator": payload.network_operator,
        "opponent_category": payload.opponent_category,
        "opponent_name": payload.opponent_name,
    }
    try:
        agent_app = await get_agent_app()
        await agent_app.aupdate_state(config, confirmed_update)
        await agent_app.ainvoke(None, config=config)
    except Exception as exc:
        logger.error("Graph-Resume fehlgeschlagen (Case %s): %s", case_id, exc)
        raise HTTPException(status_code=500, detail="Bestätigung fehlgeschlagen.")

    logger.info("Case %s: Analyse bestätigt (MaLo=%s, Zähler=%s).", case_id, payload.malo_id, payload.meter_number)

    return ConfirmAnalysisResponse(status="confirmed", next_step="timeline")


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


# ── GET /cases/{case_id}/extraction-result ────────────────────────────────────


@router.get("/{case_id}/extraction-result", response_model=ExtractionResultResponse)
def get_extraction_result(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> ExtractionResultResponse:
    """
    Gibt alle extrahierten Felder mit Confidence-Scores zurück (US-9.2).

    Liefert Felder mit needs_review/auto_accepted-Flag für die Split-View.
    Wirft 404 solange die Analyse noch nicht abgeschlossen ist.

    Raises:
        HTTPException 404: Analyse noch nicht abgeschlossen.
    """
    case = _get_owned_case(case_id, current_user, db)
    data = case.extracted_data or {}

    if not data or "extracted_at" not in data:
        raise HTTPException(status_code=404, detail="Analyse noch nicht abgeschlossen.")

    field_confidences: dict = data.get("field_confidences", {})
    source_snippets: dict = data.get("source_snippets", {})
    source_doc_ids: dict = data.get("source_doc_ids", {})

    CONFIDENCE_THRESHOLD = 0.8

    def _make_field(key: str, value: object) -> ExtractionFieldResponse:
        confidence = field_confidences.get(key, 0.6 if value is not None else 0.0)
        return ExtractionFieldResponse(
            key=key,
            value=value,
            confidence=confidence,
            needs_review=confidence < CONFIDENCE_THRESHOLD,
            auto_accepted=confidence >= CONFIDENCE_THRESHOLD and value is not None,
            source_document_id=source_doc_ids.get(key),
            source_text_snippet=source_snippets.get(key),
        )

    fields = [
        _make_field("malo_id", data.get("malo_id")),
        _make_field("meter_number", data.get("meter_number")),
        _make_field("dispute_amount", data.get("dispute_amount")),
    ]

    opponent_confidence = data.get("opponent_confidence", 0.0)
    opponent = OpponentResponse(
        category=data.get("opponent_category") or case.opponent_category,
        name=data.get("opponent_name") or case.opponent_name,
        confidence=opponent_confidence,
        needs_review=opponent_confidence < CONFIDENCE_THRESHOLD,
    )

    return ExtractionResultResponse(fields=fields, opponent=opponent)


# ── PATCH /cases/{case_id} ────────────────────────────────────────────────────


@router.patch("/{case_id}", response_model=dict)
def update_case_opponent(
    case_id: str,
    payload: UpdateOpponentRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    """
    Aktualisiert Streitpartei-Kategorie und -Name (US-9.4).

    Nutzer bestätigt oder korrigiert den KI-Vorschlag über die Kategorie-Chips.

    Raises:
        HTTPException 404: Fall nicht gefunden.
    """
    case = _get_owned_case(case_id, current_user, db)

    if payload.opponent_category is not None:
        case.opponent_category = payload.opponent_category
        # Auch in extracted_data synchron halten
        data = dict(case.extracted_data or {})
        data["opponent_category"] = payload.opponent_category
        case.extracted_data = data

    if payload.opponent_name is not None:
        case.opponent_name = payload.opponent_name
        data = dict(case.extracted_data or {})
        data["opponent_name"] = payload.opponent_name
        case.extracted_data = data

    db.commit()
    logger.info(
        "Case %s: Streitpartei aktualisiert – Kategorie=%s Name=%s",
        case_id, payload.opponent_category, payload.opponent_name,
    )
    return {"status": "updated"}


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
    """Löscht alle Vektor-Embeddings des Falls aus Qdrant (DSGVO Hard-Delete)."""
    from app.core.config import get_settings
    from app.infrastructure.qdrant_client import delete_by_case

    try:
        settings = get_settings()
        delete_by_case(
            collection=settings.qdrant_collection,
            case_id=case_id,
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
    except Exception as exc:
        logger.error("Fehler beim Löschen aus Qdrant (Case %s): %s", case_id, exc)
