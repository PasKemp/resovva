"""
Chronology Builder – Erstellung der Timeline (Roter Faden).

Ordnet extrahierte Events zeitlich, erkennt Lücken (Gap-Analysis).
"""

from typing import List

from app.domain.models import ChronologyItem, DocumentInput


def build_chronology(documents: List[DocumentInput]) -> List[ChronologyItem]:
    """
    Baut aus dokumentierten Inhalten eine sortierte Chronologie.
    TODO: LLM-basierte Extraktion von Events + Datum, dann Sortierung.
    """
    return []


def detect_gaps(chronology: List[ChronologyItem]) -> List[str]:
    """
    Erkennt referenzierte aber fehlende Belege → Fragen an User.
    TODO: Heuristik oder LLM für "Einspruch vom XY fehlt".
    """
    return []
