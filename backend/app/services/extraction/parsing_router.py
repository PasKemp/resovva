"""
Parsing-Router – US-8.2: Intelligente Routing-Logik (Fallback-Trigger).

Entscheidet automatisch ob die lokale pypdf-Extraktion ausreicht
oder ob LlamaParse (Cloud-Fallback) benötigt wird.

Routing-Regeln:
  Regel 1: Datei ist .jpg oder .png → sofort LlamaParse (pypdf kann keine Bilder lesen)
  Regel 2: Datei ist PDF, aber Ø < MIN_CHARS_PER_PAGE pro Seite → LlamaParse
  Erfolgsfall: Genug Text → pypdf-Ergebnis direkt verwenden
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

from app.services.extraction.local_extractor import LocalExtractionResult

logger = logging.getLogger(__name__)

# Dateitypen die pypdf umgehen und direkt LlamaParse nutzen
IMAGE_EXTENSIONS: frozenset[str] = frozenset({"jpg", "jpeg", "png"})


@dataclass
class ParseResult:
    """
    Einheitliches Ergebnis der Parsing-Router-Entscheidung.

    Attributes:
        text: Extrahierter Text (aus pypdf oder LlamaParse).
        method: Verwendete Extraktionsmethode.
        page_count: Anzahl der Seiten (0 für Bilder).
        chars_per_page: Zeichenanzahl je Seite (leer für Bilder).
        needs_fallback: True wenn LlamaParse benötigt wird.
    """

    text: str
    method: Literal["pypdf", "llamaparse"]
    page_count: int
    chars_per_page: List[int]
    needs_fallback: bool


class ParsingRouter:
    """
    Routing-Logik für die zweistufige Textextraktions-Pipeline.

    Bewertet ob pypdf ausreicht oder ob der LlamaParse-Cloud-Fallback
    benötigt wird. Der Schwellenwert ist über die Config konfigurierbar.

    Attributes:
        min_chars_per_page: Mindestzeichenanzahl pro Seite (konfigurierbar via .env).
    """

    def __init__(self, min_chars_per_page: int = 50) -> None:
        """
        Initialisiert den Router mit konfiguriertem Schwellenwert.

        Args:
            min_chars_per_page: Unter diesem Ø-Wert wird LlamaParse getriggert.
                                Entspricht MIN_CHARS_PER_PAGE in der .env.
        """
        self.min_chars_per_page = min_chars_per_page

    def route(
        self,
        file_extension: str,
        local_result: Optional[LocalExtractionResult] = None,
    ) -> Tuple[bool, str]:
        """
        Gibt Routing-Entscheidung und menschenlesbare Begründung zurück.

        Args:
            file_extension: Dateiendung ohne Punkt, lowercase (z.B. "pdf", "jpg").
            local_result: Ergebnis der lokalen pypdf-Extraktion. None wenn noch
                          nicht versucht (z.B. bei Bildformaten).

        Returns:
            Tuple (needs_fallback: bool, reason: str) –
            needs_fallback=True bedeutet LlamaParse wird benötigt.
        """
        ext = file_extension.lower().lstrip(".")

        # Regel 1: Bildformat → pypdf kann keinen Text aus Bildern lesen
        if ext in IMAGE_EXTENSIONS:
            return True, f"Bildformat .{ext} erfordert LlamaParse (pypdf kann keine Bilder lesen)"

        # Regel 2: Keine lokale Extraktion vorhanden
        if local_result is None:
            return True, "Keine lokale Extraktion verfügbar"

        # Regel 3: pypdf hat keine Seiten extrahiert
        if not local_result.chars_per_page:
            return True, "pypdf hat keine Seiten extrahiert (PDF möglicherweise beschädigt)"

        # Regel 4: Durchschnitt unter Schwellenwert → wahrscheinlich eingescanntes PDF
        avg_chars = sum(local_result.chars_per_page) / len(local_result.chars_per_page)
        if avg_chars < self.min_chars_per_page:
            return (
                True,
                (
                    f"pypdf Ø {avg_chars:.0f} Zeichen/Seite < "
                    f"Schwelle {self.min_chars_per_page} → eingescanntes PDF erkannt"
                ),
            )

        # Erfolgsfall: pypdf-Ergebnis ist verwertbar
        return False, f"pypdf ausreichend (Ø {avg_chars:.0f} Zeichen/Seite)"
