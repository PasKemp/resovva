"""
LlamaParse-Extraktor – US-8.3: Advanced Parsing Fallback via LlamaParse.

Sendet Dokumente asynchron an die LlamaParse Cloud-API und gibt
LLM-optimierten Markdown-Text zurück.

Free-Tier: 1.000 Seiten/Tag (https://cloud.llamaindex.ai)
Timeout: 60 Sekunden (LlamaParse kann bei großen Scans dauern)
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Timeout in Sekunden für LlamaParse API-Calls
LLAMAPARSE_TIMEOUT_SECONDS: int = 60


# ── Strukturierte Fehler-Hierarchie ───────────────────────────────────────────


class LlamaParseTimeoutError(Exception):
    """LlamaParse hat innerhalb des Timeout-Limits nicht geantwortet."""


class LlamaParseQuotaError(Exception):
    """LlamaParse Free-Tier-Limit (1.000 Seiten/Tag) überschritten."""


class LlamaParseGenericError(Exception):
    """Allgemeiner LlamaParse API-Fehler."""


# ── Öffentliche API ────────────────────────────────────────────────────────────


async def extract_text_advanced(
    file_bytes: bytes,
    filename: str,
    api_key: str,
) -> str:
    """
    Sendet ein Dokument asynchron an LlamaParse und gibt Markdown zurück.

    LlamaParse gibt LLM-optimierten Markdown zurück, der direkt für
    RAG-Pipelines und Entitäts-Extraktion nutzbar ist.

    Args:
        file_bytes: Rohe Datei-Bytes (PDF, JPEG oder PNG).
        filename: Originaler Dateiname inkl. Endung (für MIME-Typ-Erkennung).
        api_key: LlamaParse Cloud API Key (LLAMA_CLOUD_API_KEY).

    Returns:
        LLM-optimierter Markdown-String.

    Raises:
        LlamaParseTimeoutError: API antwortet nicht innerhalb von 60 Sekunden.
        LlamaParseQuotaError: Tageslimit überschritten (HTTP 429).
        LlamaParseGenericError: Sonstige API-Fehler oder fehlendes SDK.
    """
    try:
        result = await asyncio.wait_for(
            _call_llamaparse(file_bytes, filename, api_key),
            timeout=LLAMAPARSE_TIMEOUT_SECONDS,
        )
        return result
    except asyncio.TimeoutError as exc:
        raise LlamaParseTimeoutError(
            f"LlamaParse Timeout nach {LLAMAPARSE_TIMEOUT_SECONDS}s für '{filename}'"
        ) from exc


# ── Private Helpers ────────────────────────────────────────────────────────────


async def _call_llamaparse(file_bytes: bytes, filename: str, api_key: str) -> str:
    """
    Führt den eigentlichen LlamaParse API-Call durch.

    LlamaParse SDK erwartet eine Datei auf Disk; wir nutzen ein temporäres File
    das nach dem Aufruf sicher gelöscht wird.

    Args:
        file_bytes: Rohe Datei-Bytes.
        filename: Dateiname für Suffix des temporären Files.
        api_key: API-Key für LlamaParse.

    Returns:
        Extrahierter Markdown-Text aus allen Dokumenten.

    Raises:
        LlamaParseQuotaError: Bei HTTP 429 / Quota-Fehler.
        LlamaParseGenericError: Bei Import-Fehler oder sonstigen API-Fehlern.
    """
    try:
        from llama_parse import LlamaParse
    except ImportError as exc:
        raise LlamaParseGenericError(
            "llama-parse ist nicht installiert. Bitte: pip install llama-parse"
        ) from exc

    suffix = Path(filename).suffix or ".pdf"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        parser = LlamaParse(
            api_key=api_key,
            result_type="markdown",
            verbose=False,
        )

        # LlamaParse ist synchron – in Thread-Pool ausführen um Event-Loop nicht zu blockieren
        loop = asyncio.get_event_loop()
        documents = await loop.run_in_executor(
            None,
            lambda: parser.load_data(tmp_path),
        )

        logger.info("LlamaParse: %d Dokument(e) extrahiert für '%s'.", len(documents), filename)
        return "\n\n".join(doc.text for doc in documents)

    except LlamaParseGenericError:
        raise
    except Exception as exc:
        error_msg = str(exc).lower()
        if "quota" in error_msg or "limit" in error_msg or "429" in error_msg:
            raise LlamaParseQuotaError(
                f"LlamaParse Tageslimit überschritten: {exc}"
            ) from exc
        raise LlamaParseGenericError(f"LlamaParse API-Fehler: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)
