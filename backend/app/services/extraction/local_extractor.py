"""
Lokaler Textextraktor – US-8.1: Basis-Extraktion mit pypdf.

Extrahiert Text aus digital erstellten PDFs ohne externe API-Aufrufe.
pypdf läuft im Backend-Container, keine externen Calls, Dauer: Millisekunden.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class LocalExtractionResult:
    """
    Ergebnis der lokalen pypdf-Extraktion.

    Attributes:
        text: Vollständiger extrahierter Text aller Seiten.
        page_count: Anzahl der Seiten im Dokument.
        chars_per_page: Zeichenanzahl je Seite (inklusive leerer Seiten mit 0).
        method: Verwendete Extraktionsmethode (immer "pypdf").
    """

    text: str
    page_count: int
    chars_per_page: List[int]
    method: str = field(default="pypdf")


def extract_text_local(file_bytes: bytes) -> LocalExtractionResult:
    """
    Extrahiert Text aus einem PDF via pypdf (lokal, kostenlos).

    Iteriert über alle Seiten und wendet Whitespace-Normalisierung an.
    Leere Seiten werden mitgezählt (chars_per_page enthält 0-Werte),
    damit der Routing-Durchschnitt korrekt berechnet wird.

    Args:
        file_bytes: Rohe PDF-Bytes (z.B. aus S3 heruntergeladen).

    Returns:
        LocalExtractionResult mit Text, Seitenanzahl und Zeichen-je-Seite.

    Raises:
        ValueError: Wenn die Bytes kein valides PDF darstellen.
    """
    try:
        import pypdf
    except ImportError as exc:
        raise ImportError("pypdf ist nicht installiert. Bitte: pip install pypdf") from exc

    try:
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError(f"Ungültiges PDF: {exc}") from exc

    pages_text: List[str] = []
    chars_per_page: List[int] = []

    for page in reader.pages:
        raw = page.extract_text() or ""
        cleaned = _normalize_whitespace(raw)
        pages_text.append(cleaned)
        chars_per_page.append(len(cleaned))

    full_text = "\n\n".join(p for p in pages_text if p)

    logger.debug(
        "pypdf: %d Seiten, %d Zeichen gesamt, Ø %.1f/Seite.",
        len(reader.pages),
        len(full_text),
        sum(chars_per_page) / len(chars_per_page) if chars_per_page else 0,
    )

    return LocalExtractionResult(
        text=full_text,
        page_count=len(reader.pages),
        chars_per_page=chars_per_page,
    )


# ── Private Helpers ────────────────────────────────────────────────────────────


def _normalize_whitespace(text: str) -> str:
    """
    Entfernt überflüssige Leerzeilen und normalisiert Whitespace.

    Mehrere aufeinanderfolgende Leerzeilen werden auf eine reduziert.

    Args:
        text: Rohtext einer PDF-Seite.

    Returns:
        Bereinigter Text ohne übermäßige Leerzeilen.
    """
    lines = text.splitlines()
    result: List[str] = []
    prev_empty = False

    for line in lines:
        stripped = line.strip()
        is_empty = not stripped
        if is_empty and prev_empty:
            continue
        result.append(stripped)
        prev_empty = is_empty

    return "\n".join(result).strip()
