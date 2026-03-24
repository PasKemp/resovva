"""
OCR-Worker – Epic 2 (US-2.4): Asynchrone Textextraktion aus Dokumenten.

Fallback-Logik:
  Stufe 1: pypdf (kostenlos, für digitale PDFs)
  Stufe 2: Azure Document Intelligence (nur bei Bild-PDFs / JPEGs / PNGs,
           wenn pypdf weniger als 50 zusammenhängende Zeichen extrahiert)

Ablauf nach erfolgreichem S3-Upload:
  1. Dokument aus S3 herunterladen
  2. Stufe-1: pypdf-Extraktion versuchen
  3. Falls < 50 Zeichen → Stufe-2: Azure Document Intelligence
  4. PII-Maskierung (IBAN, E-Mail) anwenden
  5. masked_text + ocr_status im DB-Feld des Dokuments speichern

ocr_status-Werte:
  "pending"    – noch nicht verarbeitet (Initialzustand)
  "processing" – Extraktion läuft
  "completed"  – masked_text verfügbar
  "error"      – Fehler bei Extraktion
"""

import io
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.masking import mask_pii
from app.domain.models.db import Document
from app.infrastructure.database import get_db_context
from app.infrastructure.storage import get_storage

logger = logging.getLogger(__name__)

# Mindest-Zeichenlänge für verwertbaren pypdf-Text (Fallback-Schwelle)
_MIN_TEXT_LEN = 50


def run_ocr(document_id: str) -> None:
    """
    Führt die vollständige OCR-Pipeline für ein Dokument aus.

    Wird als FastAPI BackgroundTask nach dem Upload gestartet.
    Öffnet eine eigene DB-Session (nicht die Request-Session).

    Args:
        document_id: UUID des zu verarbeitenden Dokuments.
    """
    with get_db_context() as db:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error("OCR: Dokument %s nicht gefunden.", document_id)
            return

        doc.ocr_status = "processing"
        db.commit()

        try:
            raw_bytes = get_storage().download_file(doc.s3_key)
            raw_text  = _extract_text(raw_bytes, doc.s3_key)
            masked    = mask_pii(raw_text)

            doc.masked_text = masked
            doc.ocr_status  = "completed"
            logger.info("OCR abgeschlossen: %s (%d Zeichen)", document_id, len(masked))
        except Exception as exc:
            doc.ocr_status = "error"
            logger.error("OCR-Fehler für Dokument %s: %s", document_id, exc)

        db.commit()


# ── Textextraktion ─────────────────────────────────────────────────────────────

def _extract_text(data: bytes, s3_key: str) -> str:
    """
    Extrahiert Text aus PDF- oder Bild-Bytes.

    Stufe 1: pypdf (nur bei PDFs sinnvoll)
    Stufe 2: Azure Document Intelligence (Fallback)
    """
    ext = s3_key.rsplit(".", 1)[-1].lower() if "." in s3_key else ""

    # Stufe 1: pypdf (nur für PDFs)
    if ext == "pdf":
        text = _extract_pypdf(data)
        if len(text.strip()) >= _MIN_TEXT_LEN:
            return text
        logger.info("pypdf-Extraktion unzureichend (%d Zeichen) → Azure Fallback", len(text.strip()))

    # Stufe 2: Azure Document Intelligence
    return _extract_azure(data, ext)


def _extract_pypdf(data: bytes) -> str:
    """Extrahiert Text aus einem PDF via pypdf (kostenlos, lokal)."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(data))
        pages  = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    except Exception as exc:
        logger.warning("pypdf-Fehler: %s", exc)
        return ""


def _extract_azure(data: bytes, ext: str) -> str:
    """
    Extrahiert Text via Azure Document Intelligence (OCR für Bilder/Scans).

    Erfordert:
      AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT und AZURE_DOCUMENT_INTELLIGENCE_KEY
      in der .env-Konfiguration.

    Gibt leeren String zurück wenn Azure nicht konfiguriert ist.
    """
    from app.core.config import get_settings
    settings = get_settings()

    if not settings.azure_document_intelligence_endpoint or not settings.azure_document_intelligence_key:
        logger.warning("Azure Document Intelligence nicht konfiguriert – OCR übersprungen.")
        return ""

    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential

        client = DocumentIntelligenceClient(
            endpoint=settings.azure_document_intelligence_endpoint,
            credential=AzureKeyCredential(settings.azure_document_intelligence_key),
        )

        content_type_map = {
            "pdf":  "application/pdf",
            "jpg":  "image/jpeg",
            "jpeg": "image/jpeg",
            "png":  "image/png",
        }
        content_type = content_type_map.get(ext, "application/octet-stream")

        poller = client.begin_analyze_document(
            "prebuilt-read",
            analyze_request=data,
            content_type=content_type,
        )
        result = poller.result()

        lines = []
        for page in result.pages or []:
            for line in page.lines or []:
                lines.append(line.content)
        return "\n".join(lines)

    except Exception as exc:
        logger.error("Azure Document Intelligence Fehler: %s", exc)
        return ""
