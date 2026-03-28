"""
Dossier generation service.

Loads case and user data, populates the 'dossier_main.html' Jinja2 template,
and renders it to a PDF using WeasyPrint.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

from app.domain.exceptions import InternalServerError

if TYPE_CHECKING:
    from app.domain.models.db import Case, User

logger = logging.getLogger(__name__)

# Directory containing HTML templates
_TEMPLATE_DIR: Path = Path(__file__).parent.parent / "templates"

# Mapping of opponent categories to human-readable German labels
CATEGORY_LABELS: Dict[str, str] = {
    "strom":                "Energieversorger (Strom)",
    "gas":                  "Energieversorger (Gas)",
    "wasser":               "Wasserversorger",
    "versicherung":         "Versicherung",
    "mobilfunk_internet":   "Mobilfunk / Internet",
    "amt_behoerde":         "Amt / Behörde",
    "vermieter_immobilien": "Vermieter / Immobilien",
    "sonstiges":            "Sonstige Streitpartei",
}


def _get_jinja_env():
    """
    Initialize and return the Jinja2 environment.

    Returns:
        jinja2.Environment: Configured Jinja2 environment.
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def _render_pdf(html_string: str) -> bytes:
    """
    Render HTML string to PDF bytes using WeasyPrint.

    If WeasyPrint is not available (common in local development environments
    without system libraries), a minimal dummy PDF is returned.

    Args:
        html_string: The full HTML content to render.

    Returns:
        bytes: The rendered PDF document.

    Raises:
        InternalServerError: If rendering fails unexpectedly.
    """
    try:
        from weasyprint import HTML  # type: ignore[import-untyped]
        return HTML(string=html_string, base_url=str(_TEMPLATE_DIR)).write_pdf()
    except ImportError:
        logger.warning(
            "WeasyPrint not available. Using minimal dummy PDF for development."
        )
        return _minimal_dummy_pdf()
    except Exception as exc:
        logger.error(
            "WeasyPrint rendering failed",
            extra={"error": str(exc)},
            exc_info=True
        )
        raise InternalServerError(f"Failed to render PDF: {str(exc)}")


def _minimal_dummy_pdf() -> bytes:
    """
    Create a syntactically minimal valid PDF for development fallback.

    Returns:
        bytes: A minimalist PDF document.
    """
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
    Generator for the main dossier PDF (covering letter + chronology).
    """

    def __init__(self) -> None:
        """Initialize the generator with a Jinja2 environment."""
        self._env = _get_jinja_env()

    def generate(
        self,
        case: "Case",
        user: "User",
        timeline_events: List[Dict[str, Any]],
    ) -> bytes:
        """
        Generate the dossier PDF document.

        Args:
            case: The SQLAlchemy Case model instance.
            user: The SQLAlchemy User model instance.
            timeline_events: List of event dictionaries for the chronology.

        Returns:
            bytes: The generated PDF document.

        Raises:
            InternalServerError: If PDF generation fails.
        """
        data = case.extracted_data or {}
        category = case.opponent_category or data.get("opponent_category") or "sonstiges"

        template_ctx = {
            "case_id":              str(case.id)[-8:].upper(),
            "generated_at":         datetime.now(timezone.utc).strftime("%d.%m.%Y"),
            "user_name":            f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "opponent_name":        case.opponent_name or data.get("opponent_name") or "",
            "opponent_category":    category,
            "opponent_category_label": CATEGORY_LABELS.get(category, category),
            "meter_number":         data.get("meter_number"),
            "malo_id":              data.get("malo_id"),
            "dispute_amount":       data.get("dispute_amount"),
            "network_operator":     data.get("network_operator"),
            "document_count":       len(case.documents) if hasattr(case, "documents") else 0,
            "timeline_events":      timeline_events,
        }

        try:
            template = self._env.get_template("dossier_main.html")
            rendered_html = template.render(**template_ctx)

            logger.info("Dossier HTML rendered successfully", extra={"case_id": str(case.id)})
            pdf_bytes = _render_pdf(rendered_html)
            logger.info(
                "Dossier PDF generated",
                extra={"case_id": str(case.id), "size": len(pdf_bytes)}
            )
            return pdf_bytes
        except Exception as exc:
            logger.error(
                "Failed to generate dossier",
                extra={"case_id": str(case.id), "error": str(exc)},
                exc_info=True
            )
            raise InternalServerError(f"Dossier generation failed: {str(exc)}")


def render_dossier_ready_email(
    user_name: str,
    case_id: str,
    dashboard_url: str,
) -> str:
    """
    Render the HTML content for the 'dossier ready' notification email.

    Args:
        user_name: Full name of the user.
        case_id: The case ID (full UUID string).
        dashboard_url: Public URL to the dashboard for download.

    Returns:
        str: Rendered HTML email body.
    """
    env = _get_jinja_env()
    template = env.get_template("email_dossier_ready.html")
    return template.render(
        user_name=user_name,
        case_id=case_id[-8:].upper(),
        generated_at=datetime.now(timezone.utc).strftime("%d.%m.%Y"),
        dashboard_url=dashboard_url,
    )
