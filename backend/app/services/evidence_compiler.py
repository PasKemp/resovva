"""
EvidenceCompiler – US-6.3 (Epic 6).

Lädt Original-Dokumente aus S3, konvertiert Bilder (JPG/PNG) zu A4-PDF,
stempelt jede Anlage mit rotem "Anlage N"-Label (oben rechts) und merged
alle PDFs zu einem einzigen Master-PDF.

Reihenfolge: [Haupt-PDF, Anlage 1, Anlage 2, …]
Finales PDF wird unter ``{case_id}/dossier_master.pdf`` in S3 gespeichert.

Stempeln per pypdf + reportlab (Canvas-Overlay).
Falls reportlab nicht verfügbar, wird pypdf-only-Stempel als Fallback genutzt.
"""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

from pypdf import PdfReader, PdfWriter

from app.infrastructure.storage import get_storage

if TYPE_CHECKING:
    from app.domain.models.db import Document

logger = logging.getLogger(__name__)

# A4-Maße in Punkten (72 pt = 1 inch; A4 = 210×297 mm)
A4_WIDTH_PT  = 595.28
A4_HEIGHT_PT = 841.89


def _image_to_pdf_bytes(image_bytes: bytes) -> bytes:
    """
    Konvertiert ein JPG- oder PNG-Bild in ein A4-PDF (Bytes).

    Das Bild wird skaliert, um in A4 zu passen (mit Rand), und zentriert.
    """
    from PIL import Image  # type: ignore[import-untyped]

    img = Image.open(io.BytesIO(image_bytes))
    # RGBA → RGB für PDF-Kompatibilität
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Skalierung: maximale Nutzfläche mit 1 cm Rand
    margin_pt = 28  # 1 cm
    max_w = A4_WIDTH_PT - 2 * margin_pt
    max_h = A4_HEIGHT_PT - 2 * margin_pt

    img_w, img_h = img.size
    # Skalierungsfaktor: 1pt = 1/72 inch; bei 72 DPI entspricht 1px = 1pt
    scale = min(max_w / img_w, max_h / img_h, 1.0)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=150.0)
    return buf.getvalue()


def _stamp_pdf_page(pdf_reader: PdfReader, annex_label: str) -> PdfWriter:
    """
    Stempelt alle Seiten eines PDFs mit einem roten Annex-Label (oben rechts).

    Nutzt reportlab für das Overlay. Falls nicht verfügbar → unstamped pass-through.

    Args:
        pdf_reader:   Eingelesenes pypdf.PdfReader-Objekt.
        annex_label:  Beschriftung, z.B. "Anlage 1".

    Returns:
        pypdf.PdfWriter mit gestempelten Seiten.
    """
    writer = PdfWriter()

    try:
        from reportlab.lib.colors import red  # type: ignore[import-untyped]
        from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-untyped]
    except ImportError:
        logger.warning(
            "reportlab nicht installiert – Anlagen werden ohne Stempel zusammengeführt."
        )
        for page in pdf_reader.pages:
            writer.add_page(page)
        return writer

    for page in pdf_reader.pages:
        # Seitengröße auslesen (Fallback A4)
        media_box = page.mediabox
        page_w = float(media_box.width)
        page_h = float(media_box.height)

        # Stempel-Canvas im Speicher erzeugen
        stamp_buf = io.BytesIO()
        c = Canvas(stamp_buf, pagesize=(page_w, page_h))
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(red)

        # Position: rechts oben (1 cm Rand)
        margin = 28  # 1 cm in pt
        text_w = c.stringWidth(annex_label, "Helvetica-Bold", 10)
        x = page_w - text_w - margin
        y = page_h - margin - 12
        c.drawString(x, y, annex_label)

        # Roter Rahmen als Stempel-Box
        box_padding = 4
        c.setStrokeColor(red)
        c.setLineWidth(0.8)
        c.rect(
            x - box_padding,
            y - box_padding,
            text_w + 2 * box_padding,
            14 + 2 * box_padding,
        )

        c.save()
        stamp_buf.seek(0)

        # Stamp-PDF über Original-Seite legen
        stamp_page = PdfReader(stamp_buf).pages[0]
        page.merge_page(stamp_page)
        writer.add_page(page)

    return writer


def _bytes_to_pdf_reader(data: bytes) -> PdfReader:
    """Erstellt einen PdfReader aus Bytes."""
    return PdfReader(io.BytesIO(data))


class EvidenceCompiler:
    """
    Kompiliert Haupt-PDF + Anlage-Dokumente zu einem Master-PDF.

    Usage::

        compiler = EvidenceCompiler()
        s3_key = compiler.compile(case_id, main_pdf_bytes, documents)
    """

    def __init__(self) -> None:
        self._storage = get_storage()

    def compile(
        self,
        case_id: str,
        main_pdf_bytes: bytes,
        documents: list["Document"],
    ) -> str:
        """
        Merged Haupt-PDF + alle Anlagen zu ``{case_id}/dossier_master.pdf``.

        Reihenfolge:
        1. Haupt-PDF (Anschreiben + Chronologie)
        2. Anlage 1 … N (nach created_at sortiert)

        Bilder (jpg, jpeg, png, webp) werden vor dem Merge zu A4-PDFs konvertiert.

        Args:
            case_id:        UUID-String des Falls.
            main_pdf_bytes: Fertige Haupt-PDF-Bytes aus DossierGenerator.
            documents:      SQLAlchemy Document-Objekte des Falls.

        Returns:
            S3-Key des fertigen Master-PDFs.
        """
        master_writer = PdfWriter()

        # ── Haupt-PDF einhängen ──────────────────────────────────────────────
        main_reader = _bytes_to_pdf_reader(main_pdf_bytes)
        for page in main_reader.pages:
            master_writer.add_page(page)

        # ── Anlage-Dokumente vorbereiten ─────────────────────────────────────
        sorted_docs = sorted(documents, key=lambda d: d.created_at)
        image_exts = {".jpg", ".jpeg", ".png", ".webp"}

        for idx, doc in enumerate(sorted_docs, start=1):
            annex_label = f"Anlage {idx}"
            logger.info("EvidenceCompiler: Verarbeite %s (%s).", annex_label, doc.filename)

            try:
                file_bytes = self._storage.download_file(doc.s3_key)
            except FileNotFoundError:
                logger.warning(
                    "EvidenceCompiler: Datei nicht in S3 gefunden: %s – übersprungen.",
                    doc.s3_key,
                )
                continue
            except Exception as exc:
                logger.error("EvidenceCompiler: S3-Download-Fehler (%s): %r", doc.s3_key, exc)
                continue

            # Bild → A4-PDF konvertieren
            ext = "." + doc.filename.rsplit(".", 1)[-1].lower() if "." in doc.filename else ""
            if ext in image_exts:
                try:
                    file_bytes = _image_to_pdf_bytes(file_bytes)
                    logger.debug("EvidenceCompiler: Bild %s → PDF konvertiert.", doc.filename)
                except Exception as exc:
                    logger.error(
                        "EvidenceCompiler: Bild-Konvertierung fehlgeschlagen (%s): %r",
                        doc.filename, exc,
                    )
                    continue

            # Stempel einhängen
            try:
                annex_reader = _bytes_to_pdf_reader(file_bytes)
                stamped_writer = _stamp_pdf_page(annex_reader, annex_label)
            except Exception as exc:
                logger.error(
                    "EvidenceCompiler: Stempeln fehlgeschlagen (%s): %r",
                    doc.filename, exc,
                )
                # Fallback: unstamped
                try:
                    annex_reader = _bytes_to_pdf_reader(file_bytes)
                    stamped_writer = PdfWriter()
                    for p in annex_reader.pages:
                        stamped_writer.add_page(p)
                except Exception:
                    continue

            # Gestempelte Seiten in Master-Writer übertragen
            for page in stamped_writer.pages:
                master_writer.add_page(page)

        # ── Master-PDF serialisieren ─────────────────────────────────────────
        buf = io.BytesIO()
        master_writer.write(buf)
        master_pdf_bytes = buf.getvalue()

        # ── In S3 hochladen ──────────────────────────────────────────────────
        s3_key = f"{case_id}/dossier_master.pdf"
        self._storage.upload_file(
            data=master_pdf_bytes,
            key=s3_key,
            content_type="application/pdf",
        )
        logger.info(
            "EvidenceCompiler: Master-PDF hochgeladen – %s (%d Bytes, %d Anlagen).",
            s3_key, len(master_pdf_bytes), len(sorted_docs),
        )
        return s3_key
