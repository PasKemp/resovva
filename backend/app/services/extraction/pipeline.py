"""
Unified Extraction Pipeline – US-8.4.

Orchestriert die zweistufige Textextraktions-Pipeline und ersetzt
den Azure-basierten OCR-Worker aus US-2.4:

  Stufe 1 (lokal):  pypdf via LocalExtractor (kostenlos, ms-schnell)
  Stufe 2 (Cloud):  LlamaParse via LlamaParseExtractor (nur bei Bedarf)

Status-Flow im DB-Feld `documents.ocr_status`:
  pending → parsing → [llama_parse_fallback →] masking → completed | error

Output: einheitlicher Markdown-String → direkt an PII-Masking-Engine übergeben.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.masking import mask_pii
from app.domain.models.db import Document, LlamaParseUsage
from app.infrastructure.database import get_db_context
from app.infrastructure.storage import get_storage
from app.services.extraction.llamaparse_extractor import (
    LlamaParseGenericError,
    LlamaParseQuotaError,
    LlamaParseTimeoutError,
    extract_text_advanced,
)
from app.services.extraction.local_extractor import LocalExtractionResult, extract_text_local
from app.services.extraction.parsing_router import ParsingRouter

logger = logging.getLogger(__name__)


@dataclass
class MaskedDocument:
    """
    Ergebnis der vollständigen Extraktions-Pipeline.

    Attributes:
        document_id: UUID des verarbeiteten Dokuments.
        masked_text: PII-maskierter Text bereit für LLM-Verarbeitung.
        method: Verwendete Extraktionsmethode ("pypdf" oder "llamaparse").
        page_count: Anzahl der verarbeiteten Seiten.
    """

    document_id: str
    masked_text: str
    method: str
    page_count: int


# ── Öffentliche API ────────────────────────────────────────────────────────────


def process_document(document_id: str) -> None:
    """
    Orchestriert die vollständige Extraktions-Pipeline für ein Dokument.

    Wird als FastAPI BackgroundTask nach dem Upload gestartet.
    Öffnet eine eigene DB-Session (nicht die Request-Session).

    Status-Flow: pending → parsing → [llama_parse_fallback →] masking → completed | error

    Args:
        document_id: UUID des zu verarbeitenden Dokuments.
    """
    with get_db_context() as db:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error("Pipeline: Dokument %s nicht gefunden.", document_id)
            return

        try:
            _run_pipeline(doc, db)
        except Exception as exc:
            doc.ocr_status = "error"
            db.commit()
            logger.error("Pipeline-Fehler für Dokument %s: %s", document_id, exc)


# ── Private Pipeline-Logik ─────────────────────────────────────────────────────


def _run_pipeline(doc: Document, db: Session) -> None:
    """
    Führt die eigentliche Pipeline-Logik für ein Dokument aus.

    Stufe 1: Lokale Extraktion via pypdf (wenn PDF).
    Stufe 2: LlamaParse-Fallback (wenn Bild oder pypdf unzureichend).
    Abschluss: PII-Maskierung und DB-Speicherung.

    Args:
        doc: Das zu verarbeitende Dokument (mit aktiver DB-Session).
        db: Aktive SQLAlchemy-Session.
    """
    settings = get_settings()
    router = ParsingRouter(min_chars_per_page=settings.min_chars_per_page)

    # Status: parsing
    doc.ocr_status = "parsing"
    db.commit()

    raw_bytes = get_storage().download_file(doc.s3_key)
    ext = doc.s3_key.rsplit(".", 1)[-1].lower() if "." in doc.s3_key else ""

    # Stufe 1: Lokale pypdf-Extraktion (nur für PDFs sinnvoll)
    local_result: Optional[LocalExtractionResult] = None
    if ext == "pdf":
        try:
            local_result = extract_text_local(raw_bytes)
        except ValueError as exc:
            logger.warning("Lokale Extraktion fehlgeschlagen (%s): %s", doc.id, exc)

    # Routing-Entscheidung
    fallback_needed, reason = router.route(ext, local_result)

    if not fallback_needed and local_result:
        raw_text = local_result.text
        method = "pypdf"
        logger.info("pypdf ausreichend für %s: %s", doc.id, reason)
    else:
        logger.info("LlamaParse-Fallback für %s: %s", doc.id, reason)
        doc.ocr_status = "llama_parse_fallback"
        db.commit()

        raw_text = _run_llamaparse(doc, db, raw_bytes, settings)
        method = "llamaparse"

    # Maskierung
    doc.ocr_status = "masking"
    db.commit()

    masked = mask_pii(raw_text)
    doc.masked_text = masked
    doc.ocr_status = "completed"
    db.commit()

    logger.info(
        "Pipeline abgeschlossen: %s via %s (%d Zeichen).",
        doc.id,
        method,
        len(masked),
    )


def _run_llamaparse(
    doc: Document,
    db: Session,
    file_bytes: bytes,
    settings,
) -> str:
    """
    Führt den LlamaParse-Cloud-Fallback durch.

    Logt den Verbrauch in der llama_parse_usage-Tabelle für Free-Tier-Monitoring.
    Setzt ocr_status auf "error" bei Quota-Überschreitung (kein stilles Scheitern).

    Args:
        doc: Das zu verarbeitende Dokument.
        db: Aktive SQLAlchemy-Session.
        file_bytes: Rohe Datei-Bytes aus S3.
        settings: Anwendungskonfiguration.

    Returns:
        Extrahierter Markdown-Text (leer wenn API-Key fehlt).

    Raises:
        LlamaParseQuotaError: Bei Quota-Überschreitung (nach DB-Update).
        LlamaParseGenericError: Bei sonstigen nicht-behebbaren LlamaParse-Fehlern.
    """
    if not settings.llama_cloud_api_key:
        logger.warning("LLAMA_CLOUD_API_KEY nicht konfiguriert – LlamaParse übersprungen.")
        return ""

    filename = doc.s3_key.rsplit("/", 1)[-1]

    try:
        text = asyncio.run(
            extract_text_advanced(
                file_bytes=file_bytes,
                filename=filename,
                api_key=settings.llama_cloud_api_key,
            )
        )
        _log_llamaparse_usage(db, page_count=1)
        return text

    except LlamaParseTimeoutError as exc:
        logger.error("LlamaParse Timeout für %s: %s", doc.id, exc)
        raise LlamaParseGenericError(str(exc)) from exc

    except LlamaParseQuotaError as exc:
        logger.error("LlamaParse Quota-Fehler für %s: %s", doc.id, exc)
        doc.ocr_status = "error"
        db.commit()
        # TODO: Support-Alert auslösen (Slack/E-Mail via US-8.3 Anforderung)
        raise

    except LlamaParseGenericError:
        raise

    except Exception as exc:
        raise LlamaParseGenericError(f"Unerwarteter LlamaParse-Fehler: {exc}") from exc


def _log_llamaparse_usage(db: Session, page_count: int) -> None:
    """
    Logt LlamaParse-Verbrauch für Free-Tier-Monitoring (US-8.3).

    Addiert page_count zum heutigen Eintrag oder legt einen neuen Eintrag an.

    Args:
        db: Aktive SQLAlchemy-Session.
        page_count: Anzahl der verarbeiteten Seiten.
    """
    today = date.today()
    usage = db.query(LlamaParseUsage).filter(LlamaParseUsage.date == today).first()
    if usage:
        usage.pages_used += page_count
    else:
        db.add(LlamaParseUsage(date=today, pages_used=page_count))
    db.commit()
