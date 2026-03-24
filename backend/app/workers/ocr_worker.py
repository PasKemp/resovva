"""
OCR-Worker – Einstiegspunkt für asynchrone Dokumentenverarbeitung.

Delegiert an die Unified Extraction Pipeline (Epic 8) die pypdf + LlamaParse
als zweistufigen Fallback implementiert. Ersetzt die Azure-basierte Logik aus US-2.4.

Wird als FastAPI BackgroundTask nach erfolgreichem S3-Upload gestartet.

Status-Flow (in documents.ocr_status):
  pending → parsing → [llama_parse_fallback →] masking → completed | error
"""

import logging

from app.services.extraction.pipeline import process_document

logger = logging.getLogger(__name__)


def run_ocr(document_id: str) -> None:
    """
    Startet die vollständige Extraktions-Pipeline für ein Dokument.

    Einstiegspunkt für FastAPI BackgroundTasks; darf nicht in einer
    aktiven Request-Session aufgerufen werden.

    Args:
        document_id: UUID des zu verarbeitenden Dokuments.
    """
    process_document(document_id)
