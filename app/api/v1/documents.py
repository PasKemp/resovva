"""
API v1 – Documents: Upload & Ingestion.

Endpoints z.B.:
- POST /api/v1/documents/upload – PDF/E-Mail-Upload
- GET  /api/v1/documents/{case_id} – Dokumente eines Falls
"""

from fastapi import APIRouter, UploadFile, File

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    # case_id: str = ...,  # aus Query oder Auth
):
    """Lädt ein Dokument (PDF, .msg, .eml) hoch und startet Ingestion."""
    # TODO: Validierung, Speicherung, OCR/Parse-Pipeline anstoßen
    return {"filename": file.filename, "status": "uploaded", "message": "Placeholder"}


@router.get("/{case_id}")
async def list_documents(case_id: str):
    """Listet alle Dokumente eines Falls."""
    # TODO: aus DB/Qdrant laden
    return {"case_id": case_id, "documents": []}
