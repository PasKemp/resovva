"""
Documents Router.

Handles document lifecycle including secure uploads, MIME validation,
asynchronous OCR triggering, and AI-generated summaries.
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional, Tuple

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
)
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, get_owned_case
from app.api.v1.schemas.documents import (
    DocumentDeleteResponse,
    DocumentEntry,
    DocumentListResponse,
    DocumentUploadResponse,
    SummaryResponse,
)
from app.domain.models.db import Document
from app.infrastructure.database import get_db
from app.infrastructure.storage import get_storage
from app.workers.ocr_worker import run_ocr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["documents"])

# ── Configuration ─────────────────────────────────────────────────────────────

MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB limit

# Magic Bytes mapping: (Signature, MIME-Type, Extension)
_MAGIC_FORMATS: List[Tuple[bytes, str, str]] = [
    (b"\x25\x50\x44\x46", "application/pdf", "pdf"),
    (b"\xFF\xD8\xFF",     "image/jpeg",      "jpg"),
    (b"\x89\x50\x4E\x47", "image/png",       "png"),
]


# ── Internal Helpers ──────────────────────────────────────────────────────────

def _detect_mime(header: bytes) -> Optional[Tuple[str, str]]:
    """
    Detect MIME type and extension using magic bytes.

    Args:
        header: First 8 bytes of the file.

    Returns:
        Optional[Tuple[str, str]]: (mime_type, extension) if detected.
    """
    for magic, mime, ext in _MAGIC_FORMATS:
        if header.startswith(magic):
            return mime, ext
    return None


def _get_preview(text: Optional[str], max_chars: int = 2500) -> Optional[str]:
    """
    Generate a text preview without cutting words in the middle.

    Args:
        text: The source text.
        max_chars: Maximum length of the preview.

    Returns:
        Optional[str]: The truncated preview.
    """
    if not text or len(text) <= max_chars:
        return text
    
    cut = text[:max_chars]
    last_space = cut.rfind(" ")
    # Only cut at space if it's within a reasonable distance from the end
    return cut[:last_space] if last_space > (max_chars // 2) else cut


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/{case_id}/documents", status_code=201, response_model=DocumentUploadResponse)
async def upload_document(
    case_id: str,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    """
    Securely upload a document to S3 and register it in the database.

    Validation includes size checks, MIME-type verification (magic bytes),
    and case ownership verification. Triggers async OCR pipeline.

    Args:
        case_id: UUID of the target case.
        file: The uploaded file (PDF, JPG, PNG, or TXT).

    Returns:
        DocumentUploadResponse: Metadata including OCR status.

    Raises:
        HTTPException:
            413: File exceeds the 10 MB size limit.
            415: Unsupported file format or invalid text encoding.
            500: Internal storage failure.
    """
    case = get_owned_case(case_id, current_user, db)

    # 1. Read content for validation
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        logger.warning(
            "Upload rejected: file exceeds size limit",
            extra={"case_id": case_id, "size": len(content)}
        )
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {MAX_FILE_SIZE // (1024 * 1024)} MB."
        )

    # 2. Format validation
    mime_result = _detect_mime(content[:8])
    if mime_result:
        mime_type, extension = mime_result
    else:
        # Fallback for plain text files
        filename_lower = (file.filename or "").lower()
        if filename_lower.endswith(".txt"):
            try:
                content.decode("utf-8")
                mime_type, extension = "text/plain", "txt"
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=415,
                    detail="Text file is not valid UTF-8."
                )
        else:
            raise HTTPException(
                status_code=415,
                detail="Unsupported format. Allowed: PDF, JPEG, PNG, TXT."
            )

    # 3. Storage and Database Registration
    doc_id = uuid.uuid4()
    s3_key = f"{case.id}/{doc_id}.{extension}"
    filename = file.filename or f"document_{doc_id}.{extension}"

    storage = get_storage()
    try:
        storage.upload_file(data=content, key=s3_key, content_type=mime_type)
    except Exception as exc:
        logger.error(
            "S3 upload failed",
            extra={"case_id": case_id, "s3_key": s3_key, "error": str(exc)},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to persist file in storage.")

    document = Document(
        id=doc_id,
        case_id=case.id,
        filename=filename,
        s3_key=s3_key,
        document_type="UNKNOWN",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # 4. Trigger Async Pipeline
    background_tasks.add_task(run_ocr, str(doc_id))

    logger.info(
        "Document uploaded and registered",
        extra={"case_id": case_id, "document_id": str(doc_id)}
    )

    return DocumentUploadResponse(
        document_id=str(document.id),
        filename=document.filename,
        s3_key=document.s3_key,
        ocr_status=document.ocr_status,
        status="stored",
    )


@router.get("/{case_id}/documents", response_model=DocumentListResponse)
def list_documents(
    case_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    """
    List all documents associated with a specific case.

    Used by the frontend to poll for OCR status and display the library.

    Returns:
        DocumentListResponse: Collection of document metadata.
    """
    case = get_owned_case(case_id, current_user, db)

    return DocumentListResponse(
        documents=[
            DocumentEntry(
                document_id=str(d.id),
                filename=d.filename,
                document_type=d.document_type,
                ocr_status=d.ocr_status,
                created_at=d.created_at.isoformat(),
                # US-9.3: Return text preview for the first document in split view
                masked_text_preview=_get_preview(d.masked_text),
            )
            for d in case.documents
        ]
    )


@router.post("/{case_id}/documents/{document_id}/summarize", response_model=SummaryResponse)
async def summarize_document(
    case_id: str,
    document_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> SummaryResponse:
    """
    Generate an AI summary for a specific document.

    Uses gpt-4o-mini for a concise overview. Summaries are cached in the database.

    Args:
        case_id: UUID of the case.
        document_id: UUID of the document.

    Returns:
        SummaryResponse: The Markdown summary text or null if not enough content.
    """
    from app.agents.nodes.extract import _get_mini_llm

    case = get_owned_case(case_id, current_user, db)

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc = db.query(Document).filter(
        Document.id == doc_uuid,
        Document.case_id == case.id
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Return cached summary if available
    if doc.ai_summary:
        return SummaryResponse(summary=doc.ai_summary)

    # Guard: requires enough OCR text to be meaningful
    if not doc.masked_text or len(doc.masked_text) < 300:
        return SummaryResponse(summary=None)

    try:
        llm = _get_mini_llm()
        prompt = (
            "Analyze the following legal document (German). "
            "Create a concise summary in 3-5 bullet points. "
            "Include: document type, involved parties, key dates, amounts, and core statement. "
            "Respond in German. Each point starts with '- '.\n\n"
            f"Filename: {doc.filename}\n\n"
            f"Text:\n{doc.masked_text[:3000]}"
        )
        response = await llm.ainvoke(prompt)
        summary_text = response.content.strip()
        
        doc.ai_summary = summary_text
        db.commit()
        
        return SummaryResponse(summary=summary_text)
    except Exception as exc:
        logger.warning(
            "AI summarization failed",
            extra={"document_id": document_id, "error": str(exc)}
        )
        return SummaryResponse(summary=None)


@router.delete("/{case_id}/documents/{document_id}", response_model=DocumentDeleteResponse)
def delete_document(
    case_id: str,
    document_id: str,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> DocumentDeleteResponse:
    """
    Permanently delete a single document from S3 and the database.

    Args:
        case_id: UUID of the case.
        document_id: UUID of the document to delete.

    Returns:
        DocumentDeleteResponse: Deletion confirmation.

    Raises:
        HTTPException: If case or document is not found (404).
    """
    case = get_owned_case(case_id, current_user, db)

    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc = (
        db.query(Document)
        .filter(Document.id == doc_uuid, Document.case_id == case.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # 1. S3 Cleanup
    storage = get_storage()
    try:
        storage.delete_file(doc.s3_key)
    except Exception as exc:
        logger.error(
            "Failed to delete S3 file during document removal",
            extra={"key": doc.s3_key, "error": str(exc)}
        )

    # 2. DB Removal
    db.delete(doc)
    db.commit()

    logger.info(
        "Document deleted",
        extra={"case_id": case_id, "document_id": document_id}
    )

    return DocumentDeleteResponse(
        status="success",
        message="Document has been permanently deleted."
    )
