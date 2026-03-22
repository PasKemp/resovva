"""
Chronology Builder – Erstellung der Timeline (Roter Faden).

Ordnet extrahierte Events zeitlich, erkennt Lücken (Gap-Analysis) und
liefert eine API für den Agent-Graphen.
"""

from typing import List, Sequence

from app.domain.models import ChronologyItem, DocumentInput


def build_chronology(
    documents: Sequence[DocumentInput],
) -> List[ChronologyItem]:
    """
    Baut aus dokumentierten Inhalten eine nach Datum sortierte Chronologie.

    Nutzt aktuell Metadaten (upload_date, filename); LLM-basierte
    Event-Extraktion kann später ergänzt werden.

    Args:
        documents: Hochgeladene Dokumente mit content_text und Metadaten.

    Returns:
        Chronologisch sortierte Liste von ChronologyItem (älteste zuerst).
    """
    items: List[ChronologyItem] = []
    for doc in documents:
        items.append(
            ChronologyItem(
                date=doc.upload_date.date(),
                source_doc_id=doc.id,
                summary=doc.filename,
                original_quote=None,
                is_missing_doc=False,
            )
        )
    items.sort(key=lambda x: x.date)
    return items


def detect_gaps(chronology: Sequence[ChronologyItem]) -> List[str]:
    """
    Erkennt referenzierte aber fehlende Belege und formuliert Fragen an den User.

    Nutzt ChronologyItem.is_missing_doc; Heuristik/LLM für freitextliche
    Lücken kann später ergänzt werden.

    Args:
        chronology: Die aktuelle Chronologie (z. B. Ausgabe von build_chronology).

    Returns:
        Liste von Fragen/Hinweisen (z. B. für missing_info im Agent-State).
    """
    return [
        f"Beleg fehlt: {item.summary}"
        for item in chronology
        if item.is_missing_doc
    ]


def to_chronology_events(
    items: Sequence[ChronologyItem],
) -> List[dict]:
    """
    Mappt ChronologyItem auf das TypedDict-Format des Agent-State.

    Für die Verwendung in ResovvaState.chronology (ChronologyEvent).

    Args:
        items: Chronologie-Items aus build_chronology.

    Returns:
        Liste von Dicts mit date (str), description (str), source_doc_id (str).
    """
    return [
        {
            "date": item.date.isoformat(),
            "description": item.summary,
            "source_doc_id": item.source_doc_id,
        }
        for item in items
    ]
