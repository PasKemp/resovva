"""
Unified extraction pipeline for document processing.

Orchestrates the two-stage text extraction process:
1. Stage 1 (Local): pypdf via LocalExtractor (fast, free).
2. Stage 2 (Cloud): LlamaParse via LlamaParseExtractor (fallback for images or
   complex layouts).

Status flow in `documents.ocr_status`:
pending -> parsing -> [llama_parse_fallback ->] masking -> completed | error
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional, Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.masking import mask_pii
from app.domain.models.db import Document, LlamaParseUsage
from app.infrastructure.database import get_db_context
from app.infrastructure.storage import get_storage
from app.services.extraction.llamaparse_extractor import (
    LlamaParseGenericError,
    LlamaParseQuotaError,
    LlamaParseTimeoutError,
    extract_text_advanced,
)
from app.services.extraction.local_extractor import LocalExtractionResult, extract_text_local
from app.services.extraction.parsing_router import ParsingRouter

logger = logging.getLogger(__name__)


@dataclass
class MaskedDocument:
    """
    Result of the full extraction pipeline.

    Attributes:
        document_id: UUID of the processed document.
        masked_text: PII-masked text ready for LLM processing.
        method: Extraction method used ("pypdf", "text", or "llamaparse").
        page_count: Number of processed pages.
    """
    document_id: str
    masked_text: str
    method: str
    page_count: int


# ── Public API ────────────────────────────────────────────────────────────────

def process_document(document_id: str) -> None:
    """
    Orchestrate the full extraction pipeline for a document.

    Designed to be run as a FastAPI BackgroundTask. Opens its own database
    context to avoid session conflicts with the request-response cycle.

    Args:
        document_id: UUID of the document to process.
    """
    with get_db_context() as db:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error(
                "Pipeline: document not found",
                extra={"document_id": document_id}
            )
            return

        try:
            _run_pipeline(doc, db)
        except Exception as exc:
            doc.ocr_status = "error"
            db.commit()
            logger.error(
                "Pipeline execution failed",
                extra={"document_id": document_id, "error": str(exc)},
                exc_info=True
            )


# ── Internal Pipeline Logic ──────────────────────────────────────────────────

def _run_pipeline(doc: Document, db: Session) -> None:
    """
    Execute the core pipeline steps for a single document.

    Args:
        doc: The Document model instance (attached to active DB session).
        db: Active SQLAlchemy session.
    """
    settings = get_settings()
    router = ParsingRouter(min_chars_per_page=settings.min_chars_per_page)

    # Status: parsing
    doc.ocr_status = "parsing"
    db.commit()

    raw_bytes = get_storage().download_file(doc.s3_key)
    # Extract extension from filename or S3 key
    ext = doc.filename.rsplit(".", 1)[-1].lower() if "." in doc.filename else ""
    if not ext:
        ext = doc.s3_key.rsplit(".", 1)[-1].lower() if "." in doc.s3_key else ""

    method = "unknown"
    raw_text = ""

    # Phase 1: Direct Text or Local PDF extraction
    if ext == "txt":
        raw_text = raw_bytes.decode("utf-8", errors="replace")
        method = "text"
        logger.info("Direct text files detected (skipping OCR)", extra={"document_id": str(doc.id)})
    else:
        local_result: Optional[LocalExtractionResult] = None
        if ext == "pdf":
            try:
                local_result = extract_text_local(raw_bytes)
            except ValueError as exc:
                logger.warning(
                    "Local extraction failed",
                    extra={"document_id": str(doc.id), "error": str(exc)}
                )

        # Phase 2: Routing decision (check if LlamaParse fallback is needed)
        fallback_needed, reason = router.route(ext, local_result)

        if not fallback_needed and local_result:
            raw_text = local_result.text
            method = "pypdf"
            logger.info(
                "Local pypdf extraction successful",
                extra={"document_id": str(doc.id), "reason": reason}
            )
        else:
            logger.info(
                "Triggering LlamaParse fallback",
                extra={"document_id": str(doc.id), "reason": reason}
            )
            doc.ocr_status = "llama_parse_fallback"
            db.commit()

            raw_text = _run_llamaparse(doc, db, raw_bytes, settings)
            method = "llamaparse"

    # Phase 3: PII Masking
    doc.ocr_status = "masking"
    db.commit()

    masked = mask_pii(raw_text)
    doc.masked_text = masked
    doc.ocr_status = "completed"
    db.commit()

    logger.info(
        "Extraction pipeline completed",
        extra={
            "document_id": str(doc.id),
            "method": method,
            "char_count": len(masked)
        }
    )

    # Phase 4: RAG Embedding (US-3.1)
    _embed_document(doc, masked)


def _run_llamaparse(
    doc: Document,
    db: Session,
    file_bytes: bytes,
    settings: Any,
) -> str:
    """
    Perform cloud-based extraction via LlamaParse.

    Args:
        doc: The document to process.
        db: Active SQLAlchemy session.
        file_bytes: Raw file content.
        settings: Application settings.

    Returns:
        str: Extracted markdown text.

    Raises:
        LlamaParseQuotaError: If daily limits reached.
        LlamaParseGenericError: If API communication fails.
    """
    if not settings.llama_cloud_api_key:
        logger.warning(
            "LlamaParse API key not configured. Fallback skipped.",
            extra={"document_id": str(doc.id)}
        )
        return ""

    filename = doc.s3_key.rsplit("/", 1)[-1]

    try:
        text = asyncio.run(
            extract_text_advanced(
                file_bytes=file_bytes,
                filename=filename,
                api_key=settings.llama_cloud_api_key,
            )
        )
        _log_llamaparse_usage(db, page_count=1)  # Rough estimate
        return text

    except LlamaParseTimeoutError as exc:
        logger.error("LlamaParse timeout", extra={"document_id": str(doc.id)})
        raise LlamaParseGenericError(str(exc)) from exc

    except LlamaParseQuotaError:
        logger.error("LlamaParse quota reached", extra={"document_id": str(doc.id)})
        doc.ocr_status = "error"
        db.commit()
        raise

    except LlamaParseGenericError:
        raise

    except Exception as exc:
        raise LlamaParseGenericError(f"Unexpected LlamaParse error: {exc}") from exc


def _embed_document(doc: Document, masked_text: str) -> None:
    """
    Embed masked text into Qdrant for RAG (US-3.1).

    Args:
        doc: The document to embed.
        masked_text: PII-masked content.
    """
    try:
        from app.core.rag import chunk_and_embed

        count = chunk_and_embed(
            document_id=str(doc.id),
            case_id=str(doc.case_id),
            text=masked_text,
        )
        if count:
            logger.info(
                "RAG chunks embedded",
                extra={"document_id": str(doc.id), "count": count}
            )
    except Exception as exc:
        logger.warning(
            "RAG embedding failed",
            extra={"document_id": str(doc.id), "error": str(exc)}
        )


def _log_llamaparse_usage(db: Session, page_count: int) -> None:
    """
    Log LlamaParse usage for quota monitoring (US-8.3).

    Args:
        db: Active SQLAlchemy session.
        page_count: Estimated number of pages processed.
    """
    today = date.today()
    usage = db.query(LlamaParseUsage).filter(LlamaParseUsage.date == today).first()
    if usage:
        usage.pages_used += page_count
    else:
        db.add(LlamaParseUsage(date=today, pages_used=page_count))
    db.commit()
