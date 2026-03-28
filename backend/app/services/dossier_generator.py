"""
DossierGenerator – US-6.1 / US-6.2 (Epic 6).

Lädt Case- und User-Daten aus der DB, befüllt das Jinja2-Template
``dossier_main.html`` und rendert es via WeasyPrint zu einem PDF.

Gibt ``bytes`` zurück – kein temporäres File nötig.

WeasyPrint-Abhängigkeiten (System):
  - libpangocairo  (Text-Layout)
  - libcairo       (2D-Grafik-Library)
  - libgdk-pixbuf  (Bild-Dekodierung)
  → werden im Dockerfile für alle Stages installiert.

Dev-Modus: Falls WeasyPrint nicht importierbar ist (z.B. Windows-lokal ohne
  System-Libraries), wird ein minimales Dummy-PDF zurückgegeben damit der
  restliche Workflow (Status-Tracking, S3-Upload) trotzdem getestet werden kann.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.models.db import Case, User

logger = logging.getLogger(__name__)

# Pfad zum Template-Verzeichnis (relativ zu diesem Modul: ../../templates)
_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

# Übersetzungstabelle Opponent-Kategorie → lesbarer Name
CATEGORY_LABELS: dict[str, str] = {
    "strom":               "Energieversorger (Strom)",
    "gas":                 "Energieversorger (Gas)",
    "wasser":              "Wasserversorger",
    "versicherung":        "Versicherung",
    "mobilfunk_internet":  "Mobilfunk / Internet",
    "amt_behoerde":        "Amt / Behörde",
    "vermieter_immobilien":"Vermieter / Immobilien",
    "sonstiges":           "Sonstige Streitpartei",
}


def _get_jinja_env():
    """Gibt eine Jinja2-Environment Instanz zurück (Lazy Init)."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def _render_pdf(html_string: str) -> bytes:
    """
    Rendert einen HTML-String via WeasyPrint zu PDF-Bytes.

    Falls WeasyPrint nicht verfügbar ist (Dev ohne System-Libs), wird ein
    minmales 1-Seiten-Dummy-PDF generiert damit der Workflow getestet werden kann.
    """
    try:
        from weasyprint import HTML  # type: ignore[import-untyped]
        return HTML(string=html_string, base_url=str(_TEMPLATE_DIR)).write_pdf()
    except ImportError:
        logger.warning(
            "WeasyPrint nicht verfügbar (System-Libraries fehlen). "
            "Verwende Dummy-PDF für Dev-Modus."
        )
        return _minimal_dummy_pdf()
    except Exception as exc:
        logger.error("WeasyPrint render fehlgeschlagen: %r", exc)
        raise


def _minimal_dummy_pdf() -> bytes:
    """Erzeugt ein syntaktisch minimales valides PDF für Dev-Zwecke."""
    content = (
        "%PDF-1.4\n"
        "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]"
        "/Contents 4 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>>>endobj\n"
        "4 0 obj<</Length 52>>\n"
        "stream\n"
        "BT /F1 16 Tf 72 700 Td (Resovva Dossier - Dev Mode) Tj ET\n"
        "endstream\n"
        "endobj\n"
        "xref\n0 5\n"
        "0000000000 65535 f\n"
        "0000000009 00000 n\n"
        "0000000058 00000 n\n"
        "0000000115 00000 n\n"
        "0000000274 00000 n\n"
        "trailer<</Size 5/Root 1 0 R>>\n"
        "startxref\n376\n%%EOF"
    )
    return content.encode("latin-1")


class DossierGenerator:
    """
    Erzeugt das Haupt-PDF eines Dossiers (Deckblatt + Anschreiben + Chronologie).

    Usage::

        gen = DossierGenerator()
        pdf_bytes = gen.generate(case, user, timeline_events)
    """

    def __init__(self) -> None:
        self._env = _get_jinja_env()

    def generate(
        self,
        case: "Case",
        user: "User",
        timeline_events: list[dict],
    ) -> bytes:
        """
        Befüllt das Jinja2-Template mit Case-Daten und rendert es zu PDF.

        Args:
            case:             SQLAlchemy Case-Objekt (mit loaded extracted_data).
            user:             SQLAlchemy User-Objekt (Absender des Anschreibens).
            timeline_events:  Liste von dicts: {event_date, description, is_gap, source_type, source_doc_id}.

        Returns:
            Fertige PDF-Bytes.
        """
        data = case.extracted_data or {}
        category = case.opponent_category or data.get("opponent_category") or "sonstiges"

        template_ctx = {
            "case_id":              str(case.id)[-8:].upper(),
            "generated_at":         datetime.now(timezone.utc).strftime("%d.%m.%Y"),
            "user":                 user,
            # Streitpartei
            "opponent_name":        case.opponent_name or data.get("opponent_name") or "",
            "opponent_category":    category,
            "opponent_category_label": CATEGORY_LABELS.get(category, category),
            # Kerndaten
            "meter_number":         data.get("meter_number"),
            "malo_id":              data.get("malo_id"),
            "dispute_amount":       data.get("dispute_amount"),
            "network_operator":     data.get("network_operator"),
            "document_count":       len(case.documents) if hasattr(case, "documents") else 0,
            # Chronologie
            "timeline_events":      timeline_events,
        }

        template = self._env.get_template("dossier_main.html")
        rendered_html = template.render(**template_ctx)

        logger.info("DossierGenerator: Template gerendert für Case %s.", case.id)
        pdf_bytes = _render_pdf(rendered_html)
        logger.info(
            "DossierGenerator: PDF erzeugt – %d Bytes (Case %s).",
            len(pdf_bytes), case.id,
        )
        return pdf_bytes


def render_dossier_ready_email(
    user_name: str,
    case_id: str,
    dashboard_url: str,
) -> str:
    """
    Rendert das HTML der Benachrichtigungsmail (Dossier fertig).

    Args:
        user_name:     Vorname + Nachname des Nutzers.
        case_id:       Fall-UUID (Kurzform für E-Mail).
        dashboard_url: URL zum Dashboard / Dossier-Download.

    Returns:
        Gerendeter HTML-String für den E-Mail-Body.
    """
    env = _get_jinja_env()
    template = env.get_template("email_dossier_ready.html")
    return template.render(
        user_name=user_name,
        case_id=case_id[-8:].upper(),
        generated_at=datetime.now(timezone.utc).strftime("%d.%m.%Y"),
        dashboard_url=dashboard_url,
    )
