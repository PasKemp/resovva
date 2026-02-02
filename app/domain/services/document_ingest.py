"""
RAG/Ingest – Abstraktion für PDF- und Tabellen-Extraktion.

Backends (INGEST_BACKEND):
- text: Reiner Text-Platzhalter (keine Tabellen).
- unstructured: unstructured.io – PDF + Tabellen (pip install resovva[ingest-unstructured]).
- azure: Azure Document Intelligence – Rechnungen/Layout/Tabellen (pip install resovva[ingest-azure]).

Für Rechnungen mit Tabellen: unstructured oder azure nutzen, damit Positionen
und Zellen korrekt erkannt werden.
"""

from pathlib import Path
from typing import List, Optional

from app.core.config import get_settings


class IngestResult:
    """Ergebnis der Dokument-Extraktion: Fließtext + optionale Tabellen."""

    def __init__(
        self,
        text: str = "",
        tables: Optional[List[List[List[str]]] = None
        raw_elements: Optional[List[dict]] = None,
    ):
        self.text = text or ""
        self.tables = tables or []
        self.raw_elements = raw_elements or []


def _ingest_text(_path: Path) -> IngestResult:
    """Platzhalter: nur leerer Text (bisheriger reiner Text-Parser)."""
    return IngestResult(text="")


def _ingest_unstructured(path: Path) -> IngestResult:
    """unstructured.io: PDF + Tabellen als strukturierte Elemente."""
    try:
        from unstructured.partition.auto import partition
    except ImportError:
        return _ingest_text(path)

    elements = partition(filename=str(path))
    text_parts = []
    tables: List[List[List[str]]] = []
    raw = []

    for el in elements:
        raw.append({"type": type(el).__name__, "text": getattr(el, "text", str(el))})
        if el.category == "Table":
            # Tabellen-Struktur für Rechnungen (Zeilen/Zellen)
            if hasattr(el, "metadata") and getattr(el.metadata, "text_as_html", None):
                text_parts.append(el.text or "")
                # Einfache Zeilen-Repräsentation: Zeilen getrennt, Zellen getrennt
                rows = [row.strip().split("\t") for row in (el.text or "").split("\n") if row.strip()]
                if rows:
                    tables.append(rows)
            else:
                rows = [r.strip().split() for r in (el.text or "").split("\n") if r.strip()]
                if rows:
                    tables.append(rows)
                text_parts.append(el.text or "")
        else:
            text_parts.append(el.text or "")

    return IngestResult(
        text="\n\n".join(text_parts),
        tables=tables if tables else None,
        raw_elements=raw,
    )


def _ingest_azure(path: Path) -> IngestResult:
    """Azure Document Intelligence: Layout/Rechnung/Tabellen."""
    settings = get_settings()
    if not settings.azure_document_intelligence_endpoint or not settings.azure_document_intelligence_key:
        return _ingest_text(path)

    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.ai.documentintelligence.models import DocumentContentFormat
        from azure.core.credentials import AzureKeyCredential
    except ImportError:
        return _ingest_text(path)

    client = DocumentIntelligenceClient(
        endpoint=settings.azure_document_intelligence_endpoint,
        credential=AzureKeyCredential(settings.azure_document_intelligence_key),
    )
    with open(path, "rb") as f:
        poller = client.begin_analyze_document(
            "prebuilt-layout",
            document=f,
            output_content_format=DocumentContentFormat.MARKDOWN,
        )
    result = poller.result()

    text_parts = []
    tables: List[List[List[str]]] = []
    for doc in result.documents:
        if doc.content:
            text_parts.append(doc.content)
        for table in getattr(doc, "tables", []) or []:
            if hasattr(table, "cells") and table.cells:
                by_row: dict = {}
                for c in table.cells:
                    r, col = getattr(c, "row_index", 0), getattr(c, "column_index", 0)
                    if r not in by_row:
                        by_row[r] = {}
                    by_row[r][col] = getattr(c, "content", None) or ""
                max_col = max((max(by_row[r].keys()) for r in by_row), default=0)
                rows = [[by_row.get(r, {}).get(c, "") for c in range(max_col + 1)] for r in sorted(by_row)]
                tables.append(rows)
    return IngestResult(
        text="\n\n".join(text_parts),
        tables=tables if tables else None,
    )


def extract_document_content(path: Path) -> IngestResult:
    """
    Extrahiert Text und Tabellen aus einem Dokument (PDF etc.).
    Backend über INGEST_BACKEND (text | unstructured | azure).
    """
    backend = (get_settings().ingest_backend or "text").strip().lower()
    if backend == "unstructured":
        return _ingest_unstructured(path)
    if backend == "azure":
        return _ingest_azure(path)
    return _ingest_text(path)
