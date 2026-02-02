"""
PDF Parsing Service – Text-Extraktion aus PDFs.

CPU-bound: Nutze extract_text_from_pdf_async() in FastAPI/async-Kontext,
damit der Event-Loop nicht blockiert (läuft in Thread-Pool).
Sync-Varianten für LangGraph-Worker/Celery falls später ausgelagert.
"""

import asyncio
from pathlib import Path
from typing import Optional


def extract_text_from_pdf(file_path: Path) -> str:
    """
    Liest Text aus einer PDF-Datei (synchron, CPU-bound).
    Nutzt bei INGEST_BACKEND=unstructured|azure die RAG-Abstraktion
    (document_ingest.extract_document_content) für Text + Tabellen.
    Sonst Platzhalter; für Tabellen in Rechnungen INGEST_BACKEND setzen.
    """
    from app.core.config import get_settings

    backend = (get_settings().ingest_backend or "text").strip().lower()
    if backend in ("unstructured", "azure"):
        from app.domain.services.document_ingest import extract_document_content

        result = extract_document_content(file_path)
        return result.text or ""
    return ""


def extract_text_from_email(file_path: Path) -> str:
    """
    Liest Text aus .msg oder .eml.
    TODO: extract-msg / email-Parser.
    """
    return ""


async def extract_text_from_pdf_async(file_path: Path) -> str:
    """
    Wie extract_text_from_pdf, aber in einem Thread-Pool ausgeführt.
    In FastAPI/async-Code immer diese Funktion verwenden, um Blocking zu vermeiden.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, extract_text_from_pdf, file_path)


async def extract_text_from_email_async(file_path: Path) -> str:
    """Wie extract_text_from_email, im Thread-Pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, extract_text_from_email, file_path)
