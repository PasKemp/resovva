"""API v1 – Documents: Upload & Ingestion."""
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException

router = APIRouter(prefix="/documents", tags=["documents"])

# MVP: Temporärer lokaler Speicher.
# In Prod: S3 Bucket oder Azure Blob Storage.
UPLOAD_DIR = Path("/tmp/resovva_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    case_id: str = None,
):
    """Speichert Uploads lokal ab, damit der Agent sie greifen kann."""
    if not case_id:
        case_id = str(uuid.uuid4())

    # Filename sanitizen und mit Case-ID prefixen, um Kollisionen zu vermeiden
    safe_filename = Path(file.filename).name
    # Format: /tmp/resovva_uploads/<case_id>_Rechnung.pdf
    file_path = UPLOAD_DIR / f"{case_id}_{safe_filename}"

    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save error: {str(e)}")
    finally:
        file.file.close()

    return {
        "case_id": case_id,
        "filename": safe_filename,
        "status": "stored",
        "path": str(file_path)
    }
