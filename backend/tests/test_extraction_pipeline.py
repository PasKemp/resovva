"""
Tests für die Extraction Pipeline (Epic 8).

Abgedeckte Bereiche:
  - US-8.1: LocalExtractor (pypdf)
  - US-8.2: ParsingRouter (Routing-Logik)
  - US-8.3: LlamaParseExtractor (Fehler-Hierarchie)
  - US-8.4: Pipeline (Orchestrierung, Status-Flow, DB-Logging)

Externe Abhängigkeiten werden gemockt:
  - S3/MinIO via @patch("app.services.extraction.pipeline.get_storage")
  - LlamaParse via @patch("app.services.extraction.pipeline.extract_text_advanced")
  - mask_pii via @patch("app.services.extraction.pipeline.mask_pii")
"""

from __future__ import annotations

import io
import struct
from datetime import date
from typing import Generator
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from app.services.extraction.local_extractor import (
    LocalExtractionResult,
    _normalize_whitespace,
    extract_text_local,
)
from app.services.extraction.llamaparse_extractor import (
    LlamaParseGenericError,
    LlamaParseQuotaError,
    LlamaParseTimeoutError,
)
from app.services.extraction.parsing_router import (
    IMAGE_EXTENSIONS,
    ParsingRouter,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_pdf_bytes(text_per_page: list[str]) -> bytes:
    """Erstellt ein minimales, valides PDF mit dem gegebenen Text."""
    import pypdf
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for text in text_per_page:
        c.drawString(72, 700, text)
        c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def _make_minimal_pdf(text: str = "Hello World") -> bytes:
    """Minimales PDF via pypdf-internem Writer für einfache Tests."""
    try:
        return _make_pdf_bytes([text])
    except ImportError:
        # Fallback: raw minimal PDF wenn reportlab nicht installiert
        return (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<<>>>>\nendobj\n"
            b"4 0 obj<</Length 44>>\nstream\nBT /F1 12 Tf 100 700 Td ("
            + text.encode()
            + b") Tj ET\nendstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f \ntrailer<</Size 5/Root 1 0 R>>\n%%EOF"
        )


def _make_empty_pdf() -> bytes:
    """PDF das pypdf zwar öffnen kann, aber keinen Text enthält (simuliert Scan)."""
    import pypdf

    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.read()


def _make_jpeg_bytes() -> bytes:
    """Minimale JPEG-Magic-Bytes."""
    return b"\xFF\xD8\xFF\xE0" + b"\x00" * 20


def _make_png_bytes() -> bytes:
    """Minimale PNG-Magic-Bytes."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


# ─────────────────────────────────────────────────────────────────────────────
# US-8.1: LocalExtractor
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalizeWhitespace:
    """Tests für die interne Whitespace-Normalisierung."""

    def test_strips_leading_trailing(self):
        assert _normalize_whitespace("  hello  ") == "hello"

    def test_collapses_multiple_empty_lines(self):
        result = _normalize_whitespace("line1\n\n\n\nline2")
        assert "\n\n\n" not in result
        assert "line1" in result
        assert "line2" in result

    def test_preserves_single_empty_line(self):
        result = _normalize_whitespace("line1\n\nline2")
        assert result == "line1\n\nline2"

    def test_empty_string(self):
        assert _normalize_whitespace("") == ""

    def test_only_whitespace(self):
        assert _normalize_whitespace("   \n  \n   ") == ""


class TestExtractTextLocal:
    """Tests für extract_text_local (US-8.1)."""

    def test_raises_value_error_for_invalid_bytes(self):
        with pytest.raises(ValueError, match="Ungültiges PDF"):
            extract_text_local(b"not a pdf")

    def test_raises_value_error_for_jpeg(self):
        with pytest.raises(ValueError, match="Ungültiges PDF"):
            extract_text_local(_make_jpeg_bytes())

    def test_result_has_correct_structure(self):
        """Prüft Rückgabe-Struktur: LocalExtractionResult mit allen Feldern."""
        # Minimales leeres PDF
        pdf = _make_empty_pdf()
        result = extract_text_local(pdf)

        assert isinstance(result, LocalExtractionResult)
        assert isinstance(result.text, str)
        assert isinstance(result.page_count, int)
        assert isinstance(result.chars_per_page, list)
        assert result.method == "pypdf"
        assert result.page_count >= 1

    def test_chars_per_page_has_one_entry_per_page(self):
        pdf = _make_empty_pdf()
        result = extract_text_local(pdf)
        assert len(result.chars_per_page) == result.page_count

    def test_empty_pdf_has_zero_chars_per_page(self):
        """Eingescannte/leere PDFs sollen 0 Zeichen/Seite melden."""
        pdf = _make_empty_pdf()
        result = extract_text_local(pdf)
        # Alle chars_per_page sollten 0 sein (keine Text-Extraktion möglich)
        assert all(c == 0 for c in result.chars_per_page)

    def test_returns_pypdf_method(self):
        pdf = _make_empty_pdf()
        result = extract_text_local(pdf)
        assert result.method == "pypdf"


# ─────────────────────────────────────────────────────────────────────────────
# US-8.2: ParsingRouter
# ─────────────────────────────────────────────────────────────────────────────


class TestParsingRouterImageFormats:
    """Bilder sollen immer LlamaParse triggern (Regel 1)."""

    def setup_method(self):
        self.router = ParsingRouter(min_chars_per_page=50)

    def test_jpg_triggers_fallback(self):
        needs_fb, reason = self.router.route("jpg")
        assert needs_fb is True
        assert "jpg" in reason.lower() or "bild" in reason.lower()

    def test_jpeg_triggers_fallback(self):
        needs_fb, _ = self.router.route("jpeg")
        assert needs_fb is True

    def test_png_triggers_fallback(self):
        needs_fb, _ = self.router.route("png")
        assert needs_fb is True

    def test_uppercase_extension_triggers_fallback(self):
        needs_fb, _ = self.router.route("JPG")
        assert needs_fb is True

    def test_all_image_extensions_are_covered(self):
        for ext in IMAGE_EXTENSIONS:
            needs_fb, _ = self.router.route(ext)
            assert needs_fb is True, f"Extension {ext!r} sollte Fallback triggern"


class TestParsingRouterPdfWithoutLocalResult:
    """Ohne lokales Ergebnis wird immer Fallback getriggert."""

    def setup_method(self):
        self.router = ParsingRouter(min_chars_per_page=50)

    def test_pdf_without_local_result_triggers_fallback(self):
        needs_fb, _ = self.router.route("pdf", local_result=None)
        assert needs_fb is True

    def test_no_extension_without_local_result_triggers_fallback(self):
        needs_fb, _ = self.router.route("", local_result=None)
        assert needs_fb is True


class TestParsingRouterPdfWithLocalResult:
    """PDF-Routing basierend auf dem pypdf-Ergebnis."""

    def setup_method(self):
        self.router = ParsingRouter(min_chars_per_page=50)

    def _make_result(self, chars_per_page: list[int]) -> LocalExtractionResult:
        return LocalExtractionResult(
            text=" ".join("x" * c for c in chars_per_page),
            page_count=len(chars_per_page),
            chars_per_page=chars_per_page,
        )

    def test_sufficient_text_no_fallback(self):
        result = self._make_result([100, 200, 150])
        needs_fb, reason = self.router.route("pdf", local_result=result)
        assert needs_fb is False
        assert "pypdf" in reason.lower()

    def test_below_threshold_triggers_fallback(self):
        result = self._make_result([10, 5, 0])  # Ø = 5 < 50
        needs_fb, reason = self.router.route("pdf", local_result=result)
        assert needs_fb is True
        assert "schwelle" in reason.lower() or "50" in reason

    def test_exactly_at_threshold_no_fallback(self):
        result = self._make_result([50, 50])  # Ø = 50 >= 50
        needs_fb, _ = self.router.route("pdf", local_result=result)
        assert needs_fb is False

    def test_empty_chars_per_page_triggers_fallback(self):
        result = LocalExtractionResult(text="", page_count=1, chars_per_page=[])
        needs_fb, _ = self.router.route("pdf", local_result=result)
        assert needs_fb is True

    def test_includes_zero_pages_in_average(self):
        """Leere Seiten (0 Zeichen) müssen in den Durchschnitt einfließen."""
        # 1 Seite mit 100 Zeichen + 9 leere Seiten → Ø = 10 < 50
        result = self._make_result([100] + [0] * 9)
        needs_fb, _ = self.router.route("pdf", local_result=result)
        assert needs_fb is True

    def test_configurable_threshold(self):
        """Schwellenwert ist über Konstruktor konfigurierbar."""
        router_high = ParsingRouter(min_chars_per_page=200)
        result = self._make_result([100, 150])  # Ø = 125 < 200
        needs_fb, _ = router_high.route("pdf", local_result=result)
        assert needs_fb is True

        router_low = ParsingRouter(min_chars_per_page=10)
        needs_fb, _ = router_low.route("pdf", local_result=result)
        assert needs_fb is False


# ─────────────────────────────────────────────────────────────────────────────
# US-8.3: LlamaParseExtractor – Fehler-Hierarchie
# ─────────────────────────────────────────────────────────────────────────────


class TestLlamaParseErrorHierarchy:
    """Prüft die strukturierte Fehler-Hierarchie (US-8.3)."""

    def test_all_errors_are_exceptions(self):
        for exc_class in [LlamaParseTimeoutError, LlamaParseQuotaError, LlamaParseGenericError]:
            assert issubclass(exc_class, Exception)

    def test_errors_have_distinct_types(self):
        assert LlamaParseTimeoutError is not LlamaParseQuotaError
        assert LlamaParseQuotaError is not LlamaParseGenericError
        assert LlamaParseTimeoutError is not LlamaParseGenericError

    def test_can_raise_and_catch_timeout(self):
        with pytest.raises(LlamaParseTimeoutError, match="Timeout"):
            raise LlamaParseTimeoutError("Timeout nach 60s")

    def test_can_raise_and_catch_quota(self):
        with pytest.raises(LlamaParseQuotaError, match="Quota"):
            raise LlamaParseQuotaError("Quota exceeded")

    def test_can_raise_and_catch_generic(self):
        with pytest.raises(LlamaParseGenericError, match="API-Fehler"):
            raise LlamaParseGenericError("API-Fehler: 500")


# ─────────────────────────────────────────────────────────────────────────────
# US-8.4: Pipeline – Orchestrierung & Status-Flow
# ─────────────────────────────────────────────────────────────────────────────


def _make_mock_doc(s3_key: str = "case123/doc.pdf", doc_id: str = "doc-uuid-1") -> MagicMock:
    """Erstellt ein Mock-Dokument-Objekt."""
    doc = MagicMock()
    doc.id = doc_id
    doc.s3_key = s3_key
    doc.ocr_status = "pending"
    doc.masked_text = None
    return doc


def _make_mock_storage(file_bytes: bytes) -> MagicMock:
    """Erstellt einen Mock-Storage der file_bytes zurückgibt."""
    storage = MagicMock()
    storage.download_file.return_value = file_bytes
    return storage


def _make_mock_db(doc: MagicMock) -> MagicMock:
    """Erstellt eine Mock-DB-Session die doc bei Query zurückgibt."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = doc
    return db


class TestPipelineStatusFlow:
    """Prüft den Status-Flow: pending → parsing → ... → completed."""

    @patch("app.services.extraction.pipeline.mask_pii", return_value="masked text")
    @patch("app.services.extraction.pipeline.get_storage")
    @patch("app.services.extraction.pipeline.get_db_context")
    def test_pypdf_success_flow(self, mock_ctx, mock_storage_fn, mock_mask):
        """Erfolgspfad: pypdf liefert genug Text → direkt maskieren → completed."""
        from app.services.extraction.pipeline import process_document

        # Dokument mit genug Text (alle Seiten > 50 Zeichen)
        rich_pdf = _make_empty_pdf()  # Wir mocken local_extractor
        doc = _make_mock_doc("case/doc.pdf")

        mock_storage = _make_mock_storage(rich_pdf)
        mock_storage_fn.return_value = mock_storage

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = doc
        mock_ctx.return_value.__enter__.return_value = db

        rich_result = LocalExtractionResult(
            text="A" * 500,
            page_count=2,
            chars_per_page=[250, 250],
        )
        with patch(
            "app.services.extraction.pipeline.extract_text_local",
            return_value=rich_result,
        ):
            process_document("doc-uuid-1")

        mock_mask.assert_called_once_with("A" * 500, street=ANY, postal_code=ANY)
        assert doc.masked_text == "masked text"

    @patch("app.services.extraction.pipeline.mask_pii", return_value="masked cloud text")
    @patch("app.services.extraction.pipeline.extract_text_advanced")
    @patch("app.services.extraction.pipeline.get_storage")
    @patch("app.services.extraction.pipeline.get_db_context")
    def test_llamaparse_fallback_flow(self, mock_ctx, mock_storage_fn, mock_llama, mock_mask):
        """Fallback-Pfad: pypdf unzureichend → LlamaParse → masking → completed."""
        from app.services.extraction.pipeline import process_document

        doc = _make_mock_doc("case/scan.pdf")
        mock_storage_fn.return_value = _make_mock_storage(_make_empty_pdf())

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = doc
        mock_ctx.return_value.__enter__.return_value = db

        # pypdf liefert zu wenig Text → Fallback
        poor_result = LocalExtractionResult(
            text="",
            page_count=1,
            chars_per_page=[0],
        )

        mock_llama.return_value = "# LlamaParse Markdown"

        with (
            patch(
                "app.services.extraction.pipeline.extract_text_local",
                return_value=poor_result,
            ),
            patch(
                "app.services.extraction.pipeline.get_settings",
                return_value=MagicMock(
                    llama_cloud_api_key="test-key",
                    min_chars_per_page=50,
                ),
            ),
        ):
            process_document("doc-uuid-1")

        mock_mask.assert_called_once_with("# LlamaParse Markdown", street=ANY, postal_code=ANY)
        assert doc.masked_text == "masked cloud text"

    @patch("app.services.extraction.pipeline.get_storage")
    @patch("app.services.extraction.pipeline.get_db_context")
    def test_document_not_found(self, mock_ctx, mock_storage_fn):
        """Kein Fehler wenn Dokument nicht in DB gefunden wird."""
        from app.services.extraction.pipeline import process_document

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        mock_ctx.return_value.__enter__.return_value = db

        # Kein Exception erwartet
        process_document("non-existent-id")
        mock_storage_fn.assert_not_called()

    @patch("app.services.extraction.pipeline.mask_pii", side_effect=Exception("mask failed"))
    @patch("app.services.extraction.pipeline.get_storage")
    @patch("app.services.extraction.pipeline.get_db_context")
    def test_error_status_on_exception(self, mock_ctx, mock_storage_fn, mock_mask):
        """Bei unbehandelter Exception wird ocr_status auf 'error' gesetzt."""
        from app.services.extraction.pipeline import process_document

        doc = _make_mock_doc("case/doc.pdf")
        mock_storage_fn.return_value = _make_mock_storage(_make_empty_pdf())

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = doc
        mock_ctx.return_value.__enter__.return_value = db

        rich_result = LocalExtractionResult(
            text="A" * 500,
            page_count=1,
            chars_per_page=[500],
        )
        with patch(
            "app.services.extraction.pipeline.extract_text_local",
            return_value=rich_result,
        ):
            process_document("doc-uuid-1")

        assert doc.ocr_status == "error"


class TestPipelineImageRouting:
    """JPEG/PNG sollen pypdf überspringen und direkt LlamaParse nutzen."""

    @patch("app.services.extraction.pipeline.mask_pii", return_value="masked")
    @patch("app.services.extraction.pipeline.extract_text_advanced")
    @patch("app.services.extraction.pipeline.extract_text_local")
    @patch("app.services.extraction.pipeline.get_storage")
    @patch("app.services.extraction.pipeline.get_db_context")
    def test_jpeg_skips_pypdf(
        self, mock_ctx, mock_storage_fn, mock_local, mock_llama, mock_mask
    ):
        """JPEG-Datei darf extract_text_local nie aufrufen."""
        from app.services.extraction.pipeline import process_document

        doc = _make_mock_doc("case/photo.jpg")
        mock_storage_fn.return_value = _make_mock_storage(_make_jpeg_bytes())
        mock_llama.return_value = "cloud markdown"

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = doc
        mock_ctx.return_value.__enter__.return_value = db

        with patch(
            "app.services.extraction.pipeline.get_settings",
            return_value=MagicMock(
                llama_cloud_api_key="test-key",
                min_chars_per_page=50,
            ),
        ):
            process_document("doc-uuid-1")

        mock_local.assert_not_called()
        assert doc.masked_text == "masked"


class TestLlamaParseUsageLogging:
    """Prüft ob der LlamaParse-Verbrauch korrekt in DB geloggt wird."""

    def test_creates_new_usage_entry(self):
        """Neuer Eintrag für heutiges Datum wird angelegt."""
        from app.services.extraction.pipeline import _log_llamaparse_usage

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        _log_llamaparse_usage(db, page_count=3)

        db.add.assert_called_once()
        added_obj = db.add.call_args[0][0]
        assert added_obj.date == date.today()
        assert added_obj.pages_used == 3
        db.commit.assert_called_once()

    def test_updates_existing_usage_entry(self):
        """Vorhandener Eintrag wird um page_count erhöht."""
        from app.services.extraction.pipeline import _log_llamaparse_usage

        existing = MagicMock()
        existing.pages_used = 100

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = existing

        _log_llamaparse_usage(db, page_count=5)

        assert existing.pages_used == 105
        db.add.assert_not_called()
        db.commit.assert_called_once()


class TestPipelineQuotaHandling:
    """Bei LlamaParseQuotaError wird ocr_status auf 'error' gesetzt."""

    @patch("app.services.extraction.pipeline.get_storage")
    @patch("app.services.extraction.pipeline.get_db_context")
    def test_quota_error_sets_error_status(self, mock_ctx, mock_storage_fn):
        from app.services.extraction.pipeline import process_document

        doc = _make_mock_doc("case/scan.pdf")
        mock_storage_fn.return_value = _make_mock_storage(_make_empty_pdf())

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = doc
        mock_ctx.return_value.__enter__.return_value = db

        poor_result = LocalExtractionResult(text="", page_count=1, chars_per_page=[0])

        with (
            patch(
                "app.services.extraction.pipeline.extract_text_local",
                return_value=poor_result,
            ),
            patch(
                "app.services.extraction.pipeline.get_settings",
                return_value=MagicMock(
                    llama_cloud_api_key="test-key",
                    min_chars_per_page=50,
                ),
            ),
            patch(
                "app.services.extraction.pipeline.extract_text_advanced",
                side_effect=LlamaParseQuotaError("Quota exceeded"),
            ),
        ):
            process_document("doc-uuid-1")

        assert doc.ocr_status == "error"

    @patch("app.services.extraction.pipeline.get_storage")
    @patch("app.services.extraction.pipeline.get_db_context")
    def test_missing_api_key_returns_empty_string(self, mock_ctx, mock_storage_fn):
        """Ohne API-Key überspringt LlamaParse und gibt leeren String zurück."""
        from app.services.extraction.pipeline import process_document

        doc = _make_mock_doc("case/scan.jpg")
        mock_storage_fn.return_value = _make_mock_storage(_make_jpeg_bytes())

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = doc
        mock_ctx.return_value.__enter__.return_value = db

        with (
            patch(
                "app.services.extraction.pipeline.get_settings",
                return_value=MagicMock(
                    llama_cloud_api_key=None,
                    min_chars_per_page=50,
                ),
            ),
            patch("app.services.extraction.pipeline.mask_pii", return_value=""),
        ):
            process_document("doc-uuid-1")

        assert doc.ocr_status == "completed"
        assert doc.masked_text == ""
