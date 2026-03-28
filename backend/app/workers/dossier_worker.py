"""
DossierWorker – US-6.4 / US-6.5 (Epic 6).

Asynchroner Hintergrund-Task für die Dossier-Generierung.

Status-Flow (case.status):
  GENERATING_DOSSIER → COMPLETED  (Erfolg)
  GENERATING_DOSSIER → ERROR_GENERATION  (Fehler, Details in extracted_data["error_log"])

Sende-E-Mail via Resend nach Abschluss (graceful – Fehler stoppen den Task nicht).

Wird vom Stripe-Webhook (checkout.py) nach checkout.session.completed gestartet.
"""

from __future__ import annotations

import logging
import traceback
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def run_dossier_generation(case_id: str) -> None:
    """
    Vollständiger Dossier-Generierungs-Workflow für einen einzelnen Fall.

    1. DB-Daten laden (Case, User, ChronologyEvents)
    2. Status → GENERATING_DOSSIER setzen
    3. Haupt-PDF generieren (DossierGenerator)
    4. Anlagen kompilieren & mergen (EvidenceCompiler)
    5. Status → COMPLETED, dossier_s3_key speichern
    6. Benachrichtigungsmail versenden (Resend)

    Bei jedem unbehandelten Fehler: Status → ERROR_GENERATION + Traceback loggen.

    Args:
        case_id: UUID-String des Falls.
    """
    from app.domain.models.db import Case, ChronologyEvent, User
    from app.infrastructure.database import get_db_context
    from app.services.dossier_generator import DossierGenerator
    from app.services.evidence_compiler import EvidenceCompiler

    logger.info("DossierWorker: Gestartet für Case %s.", case_id)

    try:
        case_uuid = uuid.UUID(case_id)
    except ValueError:
        logger.error("DossierWorker: Ungültige Case-ID: %s", case_id)
        return

    # ── 1. Status sofort auf GENERATING_DOSSIER setzen ─────────────────────
    with get_db_context() as db:
        case = db.query(Case).filter(Case.id == case_uuid).first()
        if not case:
            logger.error("DossierWorker: Case %s nicht gefunden.", case_id)
            return
        case.status = "GENERATING_DOSSIER"
        db.commit()
        logger.info("DossierWorker: Status → GENERATING_DOSSIER (Case %s).", case_id)

    try:
        # ── 2. Alle benötigten Daten laden ───────────────────────────────────
        with get_db_context() as db:
            case = (
                db.query(Case)
                .filter(Case.id == case_uuid)
                .first()
            )
            if not case:
                raise RuntimeError(f"Case {case_id} nach Status-Update nicht mehr auffindbar.")

            user = db.query(User).filter(User.id == case.user_id).first()
            if not user:
                raise RuntimeError(f"User nicht gefunden für Case {case_id}.")

            timeline_events_raw = (
                db.query(ChronologyEvent)
                .filter(ChronologyEvent.case_id == case_uuid)
                .order_by(ChronologyEvent.event_date.nullslast())
                .all()
            )

            # Timeline in einfache Dicts umwandeln (außerhalb der Session nutzbar)
            timeline_events = [
                {
                    "event_date":   e.event_date.isoformat() if e.event_date else None,
                    "description":  e.description,
                    "is_gap":       e.is_gap,
                    "source_type":  e.source_type,
                    "source_doc_id": str(e.source_doc_id) if e.source_doc_id else None,
                }
                for e in timeline_events_raw
            ]

            # Dokumente für EvidenceCompiler (noch innerhalb aktiver Session merken)
            documents = list(case.documents)
            user_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            user_email = user.email

        # ── 3. Haupt-PDF generieren ──────────────────────────────────────────
        logger.info("DossierWorker: Haupt-PDF wird generiert (Case %s).", case_id)
        with get_db_context() as db:
            case_for_gen = db.query(Case).filter(Case.id == case_uuid).first()
            user_for_gen = db.query(User).filter(User.id == case_for_gen.user_id).first()
            generator = DossierGenerator()
            main_pdf_bytes = generator.generate(case_for_gen, user_for_gen, timeline_events)

        # ── 4. Anlagen-Compiler & Master-PDF ────────────────────────────────
        logger.info("DossierWorker: EvidenceCompiler läuft (Case %s).", case_id)
        with get_db_context() as db:
            case_for_compile = db.query(Case).filter(Case.id == case_uuid).first()
            docs_for_compile = list(case_for_compile.documents)

        compiler = EvidenceCompiler()
        dossier_s3_key = compiler.compile(case_id, main_pdf_bytes, docs_for_compile)

        # ── 5. Status → COMPLETED ────────────────────────────────────────────
        with get_db_context() as db:
            case = db.query(Case).filter(Case.id == case_uuid).first()
            if case:
                extracted = dict(case.extracted_data or {})
                extracted["dossier_s3_key"] = dossier_s3_key
                extracted["dossier_generated_at"] = datetime.now(timezone.utc).isoformat()
                case.extracted_data = extracted
                case.status = "COMPLETED"
                db.commit()
                logger.info("DossierWorker: Status → COMPLETED (Case %s).", case_id)

        # ── 6. Benachrichtigungsmail senden ──────────────────────────────────
        _send_dossier_ready_email(
            email=user_email,
            user_name=user_name,
            case_id=case_id,
        )

    except Exception as exc:  # pylint: disable=broad-except
        tb = traceback.format_exc()
        logger.error(
            "DossierWorker: Fehler bei Case %s: %r\n%s", case_id, exc, tb
        )
        # Status → ERROR_GENERATION + Fehlerdetails persistieren
        try:
            with get_db_context() as db:
                case = db.query(Case).filter(Case.id == case_uuid).first()
                if case:
                    extracted = dict(case.extracted_data or {})
                    extracted["error_log"] = {
                        "message": str(exc),
                        "traceback": tb[:2000],  # Max 2k Zeichen im JSONB
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    case.extracted_data = extracted
                    case.status = "ERROR_GENERATION"
                    db.commit()
                    logger.info(
                        "DossierWorker: Status → ERROR_GENERATION (Case %s).", case_id
                    )
        except Exception as db_exc:
            logger.error(
                "DossierWorker: Konnte ERROR_GENERATION nicht setzen (Case %s): %r",
                case_id, db_exc,
            )


def _send_dossier_ready_email(email: str, user_name: str, case_id: str) -> None:
    """
    Sendet die Benachrichtigungsmail via Resend SDK.

    Fehler werden nur geloggt – ein E-Mail-Problem darf die Dossier-Generierung
    nicht als fehlgeschlagen markieren.
    """
    from app.core.config import get_settings
    from app.services.dossier_generator import render_dossier_ready_email

    settings = get_settings()
    dashboard_url = f"{settings.app_base_url}/dashboard"

    html_body = render_dossier_ready_email(
        user_name=user_name,
        case_id=case_id,
        dashboard_url=dashboard_url,
    )

    if not settings.resend_api_key:
        logger.warning(
            "DossierWorker: RESEND_API_KEY nicht gesetzt – E-Mail für %s nur geloggt.", email
        )
        logger.info("DossierWorker: Dossier-fertig-Mail URL: %s", dashboard_url)
        return

    try:
        import resend  # type: ignore[import-untyped]

        resend.api_key = settings.resend_api_key
        resend.Emails.send({
            "from":    settings.email_from,
            "to":      email,
            "subject": "🎉 Dein Resovva-Dossier ist fertig!",
            "html":    html_body,
        })
        logger.info("DossierWorker: Benachrichtigungsmail gesendet an %s.", email)
    except Exception as exc:
        logger.error("DossierWorker: E-Mail-Versand fehlgeschlagen (%s): %r", email, exc)
