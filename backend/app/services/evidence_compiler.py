"""
Evidence compiler service.

Loads original documents from S3, converts images to PDF, stamps each annex
with a red 'Anlage N' label, and merges all documents into a single master PDF.
"""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, List, Set

from pypdf import PdfReader, PdfWriter

from app.infrastructure.storage import get_storage

if TYPE_CHECKING:
    from app.domain.models.db import Document

logger = logging.getLogger(__name__)

# A4 dimensions in points (72 pt = 1 inch; A4 = 210 x 297 mm)
A4_WIDTH_PT: float = 595.28
A4_HEIGHT_PT: float = 841.89


def _image_to_pdf_bytes(image_bytes: bytes) -> bytes:
    """
    Convert a JPG or PNG image into an A4 PDF.

    The image is scaled to fit within A4 margins and centered.

    Args:
        image_bytes: Raw image file content.

    Returns:
        bytes: Rendered PDF document bytes.
    """
    from PIL import Image  # type: ignore[import-untyped]

    img = Image.open(io.BytesIO(image_bytes))
    # Convert RGBA/P to RGB for PDF compatibility
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Calculate scaling: 1cm margin (approx 28pt)
    margin_pt = 28.0
    max_w = A4_WIDTH_PT - 2 * margin_pt
    max_h = A4_HEIGHT_PT - 2 * margin_pt

    img_w, img_h = img.size
    # Scaling factor: 1pt = 1/72 inch
    scale = min(max_w / img_w, max_h / img_h, 1.0)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=150.0)
    return buf.getvalue()


def _stamp_pdf_page(pdf_reader: PdfReader, annex_label: str) -> PdfWriter:
    """
    Stamp all pages of a PDF with a red annex label (top-right).

    Uses reportlab for the overlay. Falls back to unstamped pages if
    reportlab is not available.

    Args:
        pdf_reader: The pypdf Reader object containing source pages.
        annex_label: Label text, e.g., 'Anlage 1'.

    Returns:
        PdfWriter: Writer containing the stamped pages.
    """
    writer = PdfWriter()

    try:
        from reportlab.lib.colors import red  # type: ignore[import-untyped]
        from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-untyped]
    except ImportError:
        logger.warning(
            "reportlab not installed. Annexes will be merged without stamps."
        )
        for page in pdf_reader.pages:
            writer.add_page(page)
        return writer

    for page in pdf_reader.pages:
        # Get page dimensions (fallback to A4)
        media_box = page.mediabox
        page_w = float(media_box.width)
        page_h = float(media_box.height)

        # Create overlay canvas in memory
        stamp_buf = io.BytesIO()
        c = Canvas(stamp_buf, pagesize=(page_w, page_h))
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(red)

        # Position: Top-right (1cm margin)
        margin = 28.0
        text_w = c.stringWidth(annex_label, "Helvetica-Bold", 10)
        x = page_w - text_w - margin
        y = page_h - margin - 12
        c.drawString(x, y, annex_label)

        # Red border around the label
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

        # Merge the stamp overlay with the original page
        stamp_reader = PdfReader(stamp_buf)
        stamp_page = stamp_reader.pages[0]
        page.merge_page(stamp_page)
        writer.add_page(page)

    return writer


def _bytes_to_pdf_reader(data: bytes) -> PdfReader:
    """Initialize a PdfReader from bytes."""
    return PdfReader(io.BytesIO(data))


class EvidenceCompiler:
    """
    Service for compiling the dossier master PDF from multiple documents.
    """

    def __init__(self) -> None:
        """Initialize the compiler with access to S3 storage."""
        self._storage = get_storage()

    def compile(
        self,
        case_id: str,
        main_pdf_bytes: bytes,
        documents: List["Document"],
    ) -> str:
        """
        Merge the main PDF and all annexes into a single master PDF.

        Sequence:
        1. Main PDF (covering letter + chronology)
        2. Annexes 1..N (sorted by creation date)

        Args:
            case_id: UUID string of the case.
            main_pdf_bytes: Rendered main PDF bytes.
            documents: List of SQLAlchemy Document models for the case.

        Returns:
            str: S3 key of the generated master dossier.
        """
        master_writer = PdfWriter()

        # ── Attach Main PDF ──────────────────────────────────────────────────
        try:
            main_reader = _bytes_to_pdf_reader(main_pdf_bytes)
            for page in main_reader.pages:
                master_writer.add_page(page)
        except Exception as exc:
            logger.error(
                "Failed to process main PDF",
                extra={"case_id": case_id, "error": str(exc)}
            )
            # We continue even if main PDF fails (unlikely) to attempt annex merge

        # ── Process Annexes ──────────────────────────────────────────────────
        sorted_docs = sorted(documents, key=lambda d: d.created_at)
        image_extensions: Set[str] = {".jpg", ".jpeg", ".png", ".webp"}

        for idx, doc in enumerate(sorted_docs, start=1):
            annex_label = f"Anlage {idx}"
            logger.info(
                "Compiling annex",
                extra={"case_id": case_id, "label": annex_label, "filename": doc.filename}
            )

            try:
                # 1. Download from S3
                file_bytes = self._storage.download_file(doc.s3_key)

                # 2. Image to PDF conversion if needed
                ext = "." + doc.filename.rsplit(".", 1)[-1].lower() if "." in doc.filename else ""
                if ext in image_extensions:
                    file_bytes = _image_to_pdf_bytes(file_bytes)

                # 3. Apply Stamp
                annex_reader = _bytes_to_pdf_reader(file_bytes)
                stamped_writer = _stamp_pdf_page(annex_reader, annex_label)

                # 4. Add to Master
                for page in stamped_writer.pages:
                    master_writer.add_page(page)

            except Exception as exc:
                logger.error(
                    "Error processing annex",
                    extra={
                        "case_id": case_id,
                        "document_id": str(doc.id),
                        "filename": doc.filename,
                        "error": str(exc)
                    }
                )
                continue

        # ── Finalize and Upload ───────────────────────────────────────────────
        buf = io.BytesIO()
        master_writer.write(buf)
        master_pdf_bytes = buf.getvalue()

        s3_key = f"{case_id}/dossier_master.pdf"
        self._storage.upload_file(
            data=master_pdf_bytes,
            key=s3_key,
            content_type="application/pdf",
        )

        logger.info(
            "Master PDF compiled and uploaded",
            extra={
                "case_id": case_id,
                "s3_key": s3_key,
                "size": len(master_pdf_bytes),
                "annex_count": len(sorted_docs)
            }
        )
        return s3_key
