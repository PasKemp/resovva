"""
PDF Parsing Service – Text-Extraktion aus PDFs.
"""

import asyncio
from pathlib import Path

# WICHTIG: Wir nutzen jetzt immer den Ingest-Service,
# weil der intern entscheidet, ob er pypdf, unstructured oder Azure nimmt.
from app.domain.services.document_ingest import extract_document_content

def extract_text_from_pdf(file_path: Path) -> str:
    """
    Liest Text aus einer PDF-Datei (synchron, CPU-bound).
    Delegiert an document_ingest.extract_document_content.
    """
    try:
        # Hier stand vorher das "if backend ... return ''"
        # Das löschen wir, damit er IMMER deine neue pypdf-Logik nutzt.
        result = extract_document_content(file_path)

        # Kleines Debug-Print, damit du im Server-Log siehst was passiert
        print(f"DEBUG: Extracted {len(result.text)} chars from {file_path.name}")

        return result.text or ""
    except Exception as e:
        print(f"ERROR parsing PDF {file_path}: {e}")
        return ""


def extract_text_from_email(file_path: Path) -> str:
    """
    Liest Text aus .msg oder .eml.
    """
    return ""


async def extract_text_from_pdf_async(file_path: Path) -> str:
    """
    Wie extract_text_from_pdf, aber in einem Thread-Pool ausgeführt.
    In FastAPI/async-Code immer diese Funktion verwenden.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, extract_text_from_pdf, file_path)


async def extract_text_from_email_async(file_path: Path) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, extract_text_from_email, file_path)
