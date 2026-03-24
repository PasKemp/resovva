"""
Vollständige Integrationstests – Fall-Lifecycle.

Abgedeckte Endpunkte:
  POST   /api/v1/cases                              – Fall anlegen
  GET    /api/v1/cases                              – Fallliste
  DELETE /api/v1/cases/{case_id}                    – Fall löschen (DSGVO)
  GET    /api/v1/cases/{case_id}/status             – Verarbeitungsstatus
  POST   /api/v1/cases/{case_id}/analyze            – KI-Analyse starten
  POST   /api/v1/cases/{case_id}/documents          – Dokument hochladen
  GET    /api/v1/cases/{case_id}/documents          – Dokumente auflisten
  DELETE /api/v1/cases/{case_id}/documents/{doc_id} – Dokument löschen

Testbereiche:
  1.  Fall anlegen
  2.  Fallliste & Metadaten
  3.  Fall-Status-Endpunkt
  4.  Analyse-Trigger
  5.  Dokument hochladen
  6.  Dokument auflisten
  7.  Dokument löschen
  8.  Mandantenfähigkeit (Tenant Isolation)
  9.  DSGVO Hard-Delete (Fall + Dokumente)
  10. End-to-End-Lifecycle
"""

import io
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.security import hash_password
from app.domain.models.db import Case, Document, User


# ─────────────────────────────────────────────────────────────────────────────
# Testdaten-Helfer
# ─────────────────────────────────────────────────────────────────────────────

# Minimale gültige Magic-Bytes je Dateiformat
_PDF_MAGIC  = b"%PDF-1.4 minimal"         # %PDF
_JPEG_MAGIC = b"\xFF\xD8\xFF\xE0" + b"\x00" * 20  # JPEG SOI
_PNG_MAGIC  = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20  # PNG signature
_INVALID    = b"NOTAFILE" + b"\x00" * 20

def _pdf(name: str = "rechnung.pdf") -> tuple[str, tuple]:
    return ("file", (name, io.BytesIO(_PDF_MAGIC), "application/pdf"))

def _jpeg(name: str = "foto.jpg") -> tuple[str, tuple]:
    return ("file", (name, io.BytesIO(_JPEG_MAGIC), "image/jpeg"))

def _png(name: str = "scan.png") -> tuple[str, tuple]:
    return ("file", (name, io.BytesIO(_PNG_MAGIC), "image/png"))

def _invalid_file() -> tuple[str, tuple]:
    return ("file", ("virus.exe", io.BytesIO(_INVALID), "application/octet-stream"))


def _mock_storage():
    """Gibt einen Storage-Mock zurück, der S3-Calls simuliert."""
    mock = MagicMock()
    mock.upload_file.return_value = None
    mock.delete_file.return_value = None
    return mock


def _create_second_user_with_case(db) -> tuple[User, Case]:
    """Legt einen zweiten Nutzer + Fall für Tenant-Isolation-Tests an."""
    other = User(
        email="other@example.com",
        hashed_password=hash_password("passwort123"),
        accepted_terms=True,
    )
    db.add(other)
    db.commit()
    db.refresh(other)

    case = Case(user_id=other.id, status="DRAFT", extracted_data={})
    db.add(case)
    db.commit()
    db.refresh(case)
    return other, case


def _create_document_in_db(db, case: Case, ocr_status: str = "pending") -> Document:
    """Legt ein Dokument direkt in der DB an (ohne S3-Upload)."""
    doc = Document(
        case_id=case.id,
        filename="test.pdf",
        s3_key=f"{case.id}/{uuid.uuid4()}.pdf",
        document_type="UNKNOWN",
        ocr_status=ocr_status,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# 1. Fall anlegen – POST /api/v1/cases
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateCase:

    def test_create_success_returns_201(self, auth_client):
        client, _ = auth_client
        res = client.post("/api/v1/cases")
        assert res.status_code == 201

    def test_create_returns_case_id(self, auth_client):
        client, _ = auth_client
        data = client.post("/api/v1/cases").json()
        assert "case_id" in data
        # Muss gültige UUID sein
        uuid.UUID(data["case_id"])

    def test_create_initial_status_is_draft(self, auth_client):
        client, _ = auth_client
        data = client.post("/api/v1/cases").json()
        assert data["status"] == "DRAFT"

    def test_create_requires_authentication(self, client):
        res = client.post("/api/v1/cases")
        assert res.status_code == 401

    def test_create_multiple_cases_independent(self, auth_client):
        """Mehrere Fälle desselben Nutzers erhalten unterschiedliche IDs."""
        client, _ = auth_client
        id_a = client.post("/api/v1/cases").json()["case_id"]
        id_b = client.post("/api/v1/cases").json()["case_id"]
        assert id_a != id_b


# ─────────────────────────────────────────────────────────────────────────────
# 2. Fallliste & Metadaten – GET /api/v1/cases
# ─────────────────────────────────────────────────────────────────────────────

class TestListCases:

    def test_empty_list_for_new_user(self, auth_client):
        client, _ = auth_client
        res = client.get("/api/v1/cases")
        assert res.status_code == 200
        assert res.json()["cases"] == []

    def test_requires_authentication(self, client):
        res = client.get("/api/v1/cases")
        assert res.status_code == 401

    def test_created_case_appears_in_list(self, auth_client):
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        ids = [c["case_id"] for c in client.get("/api/v1/cases").json()["cases"]]
        assert case_id in ids

    def test_list_contains_all_required_fields(self, auth_client):
        client, _ = auth_client
        client.post("/api/v1/cases")
        case = client.get("/api/v1/cases").json()["cases"][0]
        for field in ("case_id", "created_at", "status", "document_count", "network_operator"):
            assert field in case, f"Fehlendes Feld: {field}"

    def test_document_count_is_zero_initially(self, auth_client):
        client, _ = auth_client
        client.post("/api/v1/cases")
        case = client.get("/api/v1/cases").json()["cases"][0]
        assert case["document_count"] == 0

    def test_network_operator_is_null_initially(self, auth_client):
        client, _ = auth_client
        client.post("/api/v1/cases")
        case = client.get("/api/v1/cases").json()["cases"][0]
        assert case["network_operator"] is None

    def test_three_cases_returns_three_entries(self, auth_client):
        client, _ = auth_client
        for _ in range(3):
            client.post("/api/v1/cases")
        assert len(client.get("/api/v1/cases").json()["cases"]) == 3

    def test_cases_sorted_newest_first(self, auth_client):
        """Neueste Fälle erscheinen zuerst in der Liste."""
        client, _ = auth_client
        first_id  = client.post("/api/v1/cases").json()["case_id"]
        second_id = client.post("/api/v1/cases").json()["case_id"]
        cases = client.get("/api/v1/cases").json()["cases"]
        assert cases[0]["case_id"] == second_id
        assert cases[1]["case_id"] == first_id

    def test_created_at_is_valid_iso_datetime(self, auth_client):
        client, _ = auth_client
        client.post("/api/v1/cases")
        case = client.get("/api/v1/cases").json()["cases"][0]
        from datetime import datetime
        # Darf nicht werfen
        datetime.fromisoformat(case["created_at"])


# ─────────────────────────────────────────────────────────────────────────────
# 3. Fall-Status – GET /api/v1/cases/{case_id}/status
# ─────────────────────────────────────────────────────────────────────────────

class TestCaseStatus:

    def test_status_empty_without_documents(self, auth_client):
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        res = client.get(f"/api/v1/cases/{case_id}/status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "empty"
        assert data["total"] == 0
        assert data["completed"] == 0

    def test_status_processing_when_document_pending(self, auth_client, db):
        client, user = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        _create_document_in_db(db, case, ocr_status="pending")

        res = client.get(f"/api/v1/cases/{case_id}/status")
        assert res.json()["status"] == "processing"

    def test_status_processing_when_document_in_ocr(self, auth_client, db):
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        _create_document_in_db(db, case, ocr_status="processing")

        res = client.get(f"/api/v1/cases/{case_id}/status")
        assert res.json()["status"] == "processing"

    def test_status_completed_when_all_docs_done(self, auth_client, db):
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        _create_document_in_db(db, case, ocr_status="completed")

        res = client.get(f"/api/v1/cases/{case_id}/status")
        data = res.json()
        assert data["status"] == "completed"
        assert data["completed"] == 1
        assert data["total"] == 1

    def test_status_error_when_document_failed(self, auth_client, db):
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        _create_document_in_db(db, case, ocr_status="error")

        res = client.get(f"/api/v1/cases/{case_id}/status")
        assert res.json()["status"] == "error"

    def test_status_processing_takes_priority_over_error(self, auth_client, db):
        """Wenn ein Dok noch läuft und ein anderes Fehler hat → 'processing'."""
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        _create_document_in_db(db, case, ocr_status="processing")
        _create_document_in_db(db, case, ocr_status="error")

        res = client.get(f"/api/v1/cases/{case_id}/status")
        assert res.json()["status"] == "processing"

    def test_status_counts_completed_documents(self, auth_client, db):
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        _create_document_in_db(db, case, ocr_status="completed")
        _create_document_in_db(db, case, ocr_status="completed")
        _create_document_in_db(db, case, ocr_status="pending")

        res = client.get(f"/api/v1/cases/{case_id}/status")
        data = res.json()
        assert data["total"] == 3
        assert data["completed"] == 2

    def test_status_requires_authentication(self, client):
        res = client.get(f"/api/v1/cases/{uuid.uuid4()}/status")
        assert res.status_code == 401

    def test_status_foreign_case_returns_404(self, auth_client, db):
        client, _ = auth_client
        _, foreign_case = _create_second_user_with_case(db)
        res = client.get(f"/api/v1/cases/{foreign_case.id}/status")
        assert res.status_code == 404

    def test_status_invalid_uuid_returns_404(self, auth_client):
        client, _ = auth_client
        res = client.get("/api/v1/cases/kein-uuid/status")
        assert res.status_code == 404

    def test_status_nonexistent_case_returns_404(self, auth_client):
        client, _ = auth_client
        res = client.get(f"/api/v1/cases/{uuid.uuid4()}/status")
        assert res.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 4. Analyse-Trigger – POST /api/v1/cases/{case_id}/analyze
# ─────────────────────────────────────────────────────────────────────────────

class TestAnalyzeTrigger:

    def test_analyze_without_documents_returns_422(self, auth_client):
        """Fall ohne Dokumente → 422 Unprocessable Entity."""
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        res = client.post(f"/api/v1/cases/{case_id}/analyze")
        assert res.status_code == 422

    def test_analyze_with_pending_documents_returns_409(self, auth_client, db):
        """Noch laufende OCR → 409 Conflict."""
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        _create_document_in_db(db, case, ocr_status="pending")

        res = client.post(f"/api/v1/cases/{case_id}/analyze")
        assert res.status_code == 409

    def test_analyze_with_processing_documents_returns_409(self, auth_client, db):
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        _create_document_in_db(db, case, ocr_status="processing")

        res = client.post(f"/api/v1/cases/{case_id}/analyze")
        assert res.status_code == 409

    def test_analyze_with_completed_documents_returns_202(self, auth_client, db):
        """OCR abgeschlossen → 202 Accepted."""
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        _create_document_in_db(db, case, ocr_status="completed")

        res = client.post(f"/api/v1/cases/{case_id}/analyze")
        assert res.status_code == 202

    def test_analyze_with_error_documents_returns_202(self, auth_client, db):
        """Dokument mit OCR-Fehler aber kein Pending → Analyse startet trotzdem."""
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        _create_document_in_db(db, case, ocr_status="error")

        res = client.post(f"/api/v1/cases/{case_id}/analyze")
        assert res.status_code == 202

    def test_analyze_requires_authentication(self, client):
        res = client.post(f"/api/v1/cases/{uuid.uuid4()}/analyze")
        assert res.status_code == 401

    def test_analyze_foreign_case_returns_404(self, auth_client, db):
        client, _ = auth_client
        _, foreign_case = _create_second_user_with_case(db)
        res = client.post(f"/api/v1/cases/{foreign_case.id}/analyze")
        assert res.status_code == 404

    def test_analyze_invalid_uuid_returns_404(self, auth_client):
        client, _ = auth_client
        res = client.post("/api/v1/cases/kein-uuid/analyze")
        assert res.status_code == 404

    def test_analyze_409_includes_pending_count(self, auth_client, db):
        """Fehlermeldung bei 409 nennt Anzahl der noch verarbeiteten Dokumente."""
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        _create_document_in_db(db, case, ocr_status="pending")
        _create_document_in_db(db, case, ocr_status="processing")

        res = client.post(f"/api/v1/cases/{case_id}/analyze")
        assert res.status_code == 409
        assert "2" in res.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# 5. Dokument hochladen – POST /api/v1/cases/{case_id}/documents
# ─────────────────────────────────────────────────────────────────────────────

class TestUploadDocument:

    @patch("app.api.v1.documents.get_storage")
    @patch("app.workers.ocr_worker.run_ocr")
    def test_upload_pdf_success(self, mock_ocr, mock_storage_factory, auth_client):
        mock_storage_factory.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        res = client.post(f"/api/v1/cases/{case_id}/documents", files=[_pdf()])
        assert res.status_code == 201

    @patch("app.api.v1.documents.get_storage")
    @patch("app.workers.ocr_worker.run_ocr")
    def test_upload_returns_document_id(self, mock_ocr, mock_storage_factory, auth_client):
        mock_storage_factory.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        data = client.post(f"/api/v1/cases/{case_id}/documents", files=[_pdf()]).json()
        assert "document_id" in data
        uuid.UUID(data["document_id"])  # muss gültige UUID sein

    @patch("app.api.v1.documents.get_storage")
    @patch("app.workers.ocr_worker.run_ocr")
    def test_upload_preserves_filename(self, mock_ocr, mock_storage_factory, auth_client):
        mock_storage_factory.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        data = client.post(
            f"/api/v1/cases/{case_id}/documents",
            files=[_pdf("meine_rechnung.pdf")]
        ).json()
        assert data["filename"] == "meine_rechnung.pdf"

    @patch("app.api.v1.documents.get_storage")
    @patch("app.workers.ocr_worker.run_ocr")
    def test_upload_jpeg_accepted(self, mock_ocr, mock_storage_factory, auth_client):
        mock_storage_factory.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        res = client.post(f"/api/v1/cases/{case_id}/documents", files=[_jpeg()])
        assert res.status_code == 201

    @patch("app.api.v1.documents.get_storage")
    @patch("app.workers.ocr_worker.run_ocr")
    def test_upload_png_accepted(self, mock_ocr, mock_storage_factory, auth_client):
        mock_storage_factory.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        res = client.post(f"/api/v1/cases/{case_id}/documents", files=[_png()])
        assert res.status_code == 201

    def test_upload_invalid_format_returns_415(self, auth_client):
        """Unbekanntes Dateiformat → 415 Unsupported Media Type."""
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        res = client.post(f"/api/v1/cases/{case_id}/documents", files=[_invalid_file()])
        assert res.status_code == 415

    def test_upload_oversized_file_returns_413(self, auth_client):
        """Datei über 10 MB → 413 Request Entity Too Large."""
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        big = ("file", ("big.pdf", io.BytesIO(_PDF_MAGIC + b"\x00" * (11 * 1024 * 1024)), "application/pdf"))
        res = client.post(f"/api/v1/cases/{case_id}/documents", files=[big])
        assert res.status_code == 413

    def test_upload_mime_spoofing_blocked(self, auth_client):
        """PDF-Dateiendung aber falsche Magic-Bytes → 415."""
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        fake = ("file", ("fake.pdf", io.BytesIO(_INVALID), "application/pdf"))
        res = client.post(f"/api/v1/cases/{case_id}/documents", files=[fake])
        assert res.status_code == 415

    def test_upload_requires_authentication(self, client):
        res = client.post(f"/api/v1/cases/{uuid.uuid4()}/documents", files=[_pdf()])
        assert res.status_code == 401

    def test_upload_to_foreign_case_returns_404(self, auth_client, db):
        client, _ = auth_client
        _, foreign_case = _create_second_user_with_case(db)
        res = client.post(f"/api/v1/cases/{foreign_case.id}/documents", files=[_pdf()])
        assert res.status_code == 404

    def test_upload_to_nonexistent_case_returns_404(self, auth_client):
        client, _ = auth_client
        res = client.post(f"/api/v1/cases/{uuid.uuid4()}/documents", files=[_pdf()])
        assert res.status_code == 404

    def test_upload_invalid_case_uuid_returns_404(self, auth_client):
        client, _ = auth_client
        res = client.post("/api/v1/cases/kein-uuid/documents", files=[_pdf()])
        assert res.status_code == 404

    @patch("app.api.v1.documents.get_storage")
    @patch("app.workers.ocr_worker.run_ocr")
    def test_upload_initial_ocr_status_is_pending(self, mock_ocr, mock_storage_factory, auth_client):
        mock_storage_factory.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        data = client.post(f"/api/v1/cases/{case_id}/documents", files=[_pdf()]).json()
        assert data["ocr_status"] == "pending"

    @patch("app.api.v1.documents.get_storage")
    @patch("app.workers.ocr_worker.run_ocr")
    def test_upload_increments_document_count(self, mock_ocr, mock_storage_factory, auth_client):
        """document_count in der Fallliste steigt nach Upload."""
        mock_storage_factory.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        client.post(f"/api/v1/cases/{case_id}/documents", files=[_pdf()])
        client.post(f"/api/v1/cases/{case_id}/documents", files=[_pdf()])

        case = next(c for c in client.get("/api/v1/cases").json()["cases"] if c["case_id"] == case_id)
        assert case["document_count"] == 2

    @patch("app.api.v1.documents.get_storage")
    def test_upload_storage_error_returns_500(self, mock_storage_factory, auth_client):
        """Storage-Fehler → 500 Internal Server Error (kein DB-Eintrag ohne S3-Upload)."""
        mock_storage = _mock_storage()
        mock_storage.upload_file.side_effect = Exception("MinIO nicht erreichbar")
        mock_storage_factory.return_value = mock_storage

        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        res = client.post(f"/api/v1/cases/{case_id}/documents", files=[_pdf()])
        assert res.status_code == 500


# ─────────────────────────────────────────────────────────────────────────────
# 6. Dokumente auflisten – GET /api/v1/cases/{case_id}/documents
# ─────────────────────────────────────────────────────────────────────────────

class TestListDocuments:

    def test_empty_list_for_new_case(self, auth_client):
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        res = client.get(f"/api/v1/cases/{case_id}/documents")
        assert res.status_code == 200
        assert res.json()["documents"] == []

    def test_document_appears_after_db_insert(self, auth_client, db):
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        doc = _create_document_in_db(db, case)

        docs = client.get(f"/api/v1/cases/{case_id}/documents").json()["documents"]
        assert len(docs) == 1
        assert docs[0]["document_id"] == str(doc.id)

    def test_document_contains_required_fields(self, auth_client, db):
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        _create_document_in_db(db, case)

        doc = client.get(f"/api/v1/cases/{case_id}/documents").json()["documents"][0]
        for field in ("document_id", "filename", "document_type", "ocr_status", "created_at"):
            assert field in doc, f"Fehlendes Feld: {field}"

    def test_multiple_documents_all_listed(self, auth_client, db):
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        _create_document_in_db(db, case)
        _create_document_in_db(db, case)
        _create_document_in_db(db, case)

        docs = client.get(f"/api/v1/cases/{case_id}/documents").json()["documents"]
        assert len(docs) == 3

    def test_list_requires_authentication(self, client):
        res = client.get(f"/api/v1/cases/{uuid.uuid4()}/documents")
        assert res.status_code == 401

    def test_list_foreign_case_returns_404(self, auth_client, db):
        client, _ = auth_client
        _, foreign_case = _create_second_user_with_case(db)
        res = client.get(f"/api/v1/cases/{foreign_case.id}/documents")
        assert res.status_code == 404

    def test_list_invalid_case_uuid_returns_404(self, auth_client):
        client, _ = auth_client
        res = client.get("/api/v1/cases/kein-uuid/documents")
        assert res.status_code == 404

    def test_ocr_status_correctly_reflected(self, auth_client, db):
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        _create_document_in_db(db, case, ocr_status="completed")

        doc = client.get(f"/api/v1/cases/{case_id}/documents").json()["documents"][0]
        assert doc["ocr_status"] == "completed"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Dokument löschen – DELETE /api/v1/cases/{case_id}/documents/{doc_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteDocument:

    @patch("app.api.v1.documents.get_storage")
    def test_delete_document_success(self, mock_storage_factory, auth_client, db):
        mock_storage_factory.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        doc = _create_document_in_db(db, case)

        res = client.delete(f"/api/v1/cases/{case_id}/documents/{doc.id}")
        assert res.status_code == 200
        assert res.json()["status"] == "success"

    @patch("app.api.v1.documents.get_storage")
    def test_document_removed_from_list_after_delete(self, mock_storage_factory, auth_client, db):
        mock_storage_factory.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        doc = _create_document_in_db(db, case)

        client.delete(f"/api/v1/cases/{case_id}/documents/{doc.id}")
        docs = client.get(f"/api/v1/cases/{case_id}/documents").json()["documents"]
        assert not any(d["document_id"] == str(doc.id) for d in docs)

    @patch("app.api.v1.documents.get_storage")
    def test_delete_only_removes_target_document(self, mock_storage_factory, auth_client, db):
        """Nach dem Löschen eines Dokuments bleiben andere erhalten."""
        mock_storage_factory.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        doc_a = _create_document_in_db(db, case)
        doc_b = _create_document_in_db(db, case)

        client.delete(f"/api/v1/cases/{case_id}/documents/{doc_a.id}")
        docs = client.get(f"/api/v1/cases/{case_id}/documents").json()["documents"]
        ids = [d["document_id"] for d in docs]
        assert str(doc_a.id) not in ids
        assert str(doc_b.id) in ids

    def test_delete_document_requires_authentication(self, client, db):
        res = client.delete(f"/api/v1/cases/{uuid.uuid4()}/documents/{uuid.uuid4()}")
        assert res.status_code == 401

    def test_delete_document_from_foreign_case_returns_404(self, auth_client, db):
        client, _ = auth_client
        _, foreign_case = _create_second_user_with_case(db)
        doc = _create_document_in_db(db, foreign_case)
        res = client.delete(f"/api/v1/cases/{foreign_case.id}/documents/{doc.id}")
        assert res.status_code == 404

    @patch("app.api.v1.documents.get_storage")
    def test_delete_nonexistent_document_returns_404(self, mock_storage_factory, auth_client):
        mock_storage_factory.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        res = client.delete(f"/api/v1/cases/{case_id}/documents/{uuid.uuid4()}")
        assert res.status_code == 404

    def test_delete_document_invalid_uuid_returns_404(self, auth_client):
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        res = client.delete(f"/api/v1/cases/{case_id}/documents/kein-uuid")
        assert res.status_code == 404

    @patch("app.api.v1.documents.get_storage")
    def test_delete_document_decrements_document_count(self, mock_storage_factory, auth_client, db):
        mock_storage_factory.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        doc_a = _create_document_in_db(db, case)
        _create_document_in_db(db, case)

        client.delete(f"/api/v1/cases/{case_id}/documents/{doc_a.id}")
        list_case = next(c for c in client.get("/api/v1/cases").json()["cases"] if c["case_id"] == case_id)
        assert list_case["document_count"] == 1

    @patch("app.api.v1.documents.get_storage")
    def test_delete_document_storage_error_still_removes_from_db(
        self, mock_storage_factory, auth_client, db
    ):
        """Storage-Fehler beim Löschen → DB-Eintrag trotzdem entfernt."""
        mock_storage = _mock_storage()
        mock_storage.delete_file.side_effect = Exception("MinIO down")
        mock_storage_factory.return_value = mock_storage

        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        doc = _create_document_in_db(db, case)

        # Kein 500 – Storage-Fehler werden geloggt, nicht weitergegeben
        res = client.delete(f"/api/v1/cases/{case_id}/documents/{doc.id}")
        assert res.status_code == 200
        docs = client.get(f"/api/v1/cases/{case_id}/documents").json()["documents"]
        assert not any(d["document_id"] == str(doc.id) for d in docs)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Mandantenfähigkeit – Tenant Isolation
# ─────────────────────────────────────────────────────────────────────────────

class TestTenantIsolation:

    def test_list_shows_only_own_cases(self, auth_client, db):
        client, _ = auth_client
        _, foreign_case = _create_second_user_with_case(db)

        ids = [c["case_id"] for c in client.get("/api/v1/cases").json()["cases"]]
        assert str(foreign_case.id) not in ids

    def test_delete_foreign_case_returns_404_not_403(self, auth_client, db):
        """404 statt 403: kein Informationsleak über die Existenz fremder Fälle."""
        client, _ = auth_client
        _, foreign_case = _create_second_user_with_case(db)
        res = client.delete(f"/api/v1/cases/{foreign_case.id}")
        assert res.status_code == 404

    def test_upload_to_foreign_case_returns_404(self, auth_client, db):
        client, _ = auth_client
        _, foreign_case = _create_second_user_with_case(db)
        res = client.post(f"/api/v1/cases/{foreign_case.id}/documents", files=[_pdf()])
        assert res.status_code == 404

    def test_list_documents_of_foreign_case_returns_404(self, auth_client, db):
        client, _ = auth_client
        _, foreign_case = _create_second_user_with_case(db)
        res = client.get(f"/api/v1/cases/{foreign_case.id}/documents")
        assert res.status_code == 404

    def test_delete_document_from_foreign_case_returns_404(self, auth_client, db):
        client, _ = auth_client
        _, foreign_case = _create_second_user_with_case(db)
        doc = _create_document_in_db(db, foreign_case)
        res = client.delete(f"/api/v1/cases/{foreign_case.id}/documents/{doc.id}")
        assert res.status_code == 404

    def test_status_of_foreign_case_returns_404(self, auth_client, db):
        client, _ = auth_client
        _, foreign_case = _create_second_user_with_case(db)
        res = client.get(f"/api/v1/cases/{foreign_case.id}/status")
        assert res.status_code == 404

    def test_analyze_foreign_case_returns_404(self, auth_client, db):
        client, _ = auth_client
        _, foreign_case = _create_second_user_with_case(db)
        res = client.post(f"/api/v1/cases/{foreign_case.id}/analyze")
        assert res.status_code == 404

    def test_cannot_delete_document_across_cases(self, auth_client, db):
        """Dokument-ID aus Fall A kann nicht über Fall B gelöscht werden."""
        client, _ = auth_client
        case_a_id = client.post("/api/v1/cases").json()["case_id"]
        case_b_id = client.post("/api/v1/cases").json()["case_id"]
        case_a = db.query(Case).filter(Case.id == uuid.UUID(case_a_id)).first()
        doc = _create_document_in_db(db, case_a)

        # doc gehört zu case_a – Löschen über case_b muss fehlschlagen
        res = client.delete(f"/api/v1/cases/{case_b_id}/documents/{doc.id}")
        assert res.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 9. DSGVO Hard-Delete – DELETE /api/v1/cases/{case_id}
# ─────────────────────────────────────────────────────────────────────────────

class TestHardDeleteCase:

    def test_delete_removes_case_from_list(self, auth_client):
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        client.delete(f"/api/v1/cases/{case_id}")
        ids = [c["case_id"] for c in client.get("/api/v1/cases").json()["cases"]]
        assert case_id not in ids

    def test_delete_returns_success(self, auth_client):
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        res = client.delete(f"/api/v1/cases/{case_id}")
        assert res.status_code == 200
        assert res.json()["status"] == "success"

    def test_delete_does_not_affect_other_cases(self, auth_client):
        client, _ = auth_client
        id_a = client.post("/api/v1/cases").json()["case_id"]
        id_b = client.post("/api/v1/cases").json()["case_id"]
        client.delete(f"/api/v1/cases/{id_a}")
        ids = [c["case_id"] for c in client.get("/api/v1/cases").json()["cases"]]
        assert id_a not in ids
        assert id_b in ids

    def test_delete_twice_returns_404(self, auth_client):
        """Zweifaches Löschen desselben Falls → 404."""
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        client.delete(f"/api/v1/cases/{case_id}")
        res = client.delete(f"/api/v1/cases/{case_id}")
        assert res.status_code == 404

    @patch("app.api.v1.cases.get_storage")
    def test_delete_case_removes_documents_from_db(self, mock_storage_factory, auth_client, db):
        """CASCADE: Dokumente werden nach Löschen des Falls aus der DB entfernt."""
        mock_storage_factory.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        doc = _create_document_in_db(db, case)
        doc_id = doc.id

        client.delete(f"/api/v1/cases/{case_id}")
        db.expire_all()
        assert db.query(Document).filter(Document.id == doc_id).first() is None

    def test_delete_requires_authentication(self, client):
        res = client.delete(f"/api/v1/cases/{uuid.uuid4()}")
        assert res.status_code == 401

    def test_delete_nonexistent_case_returns_404(self, auth_client):
        client, _ = auth_client
        res = client.delete(f"/api/v1/cases/{uuid.uuid4()}")
        assert res.status_code == 404

    def test_delete_invalid_uuid_returns_404(self, auth_client):
        client, _ = auth_client
        res = client.delete("/api/v1/cases/kein-uuid")
        assert res.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 10. End-to-End-Lifecycle
# ─────────────────────────────────────────────────────────────────────────────

class TestEndToEndLifecycle:

    @patch("app.api.v1.documents.get_storage")
    @patch("app.workers.ocr_worker.run_ocr")
    def test_full_case_creation_to_deletion(self, mock_ocr, mock_storage_factory, auth_client, db):
        """
        Vollständiger Lebenszyklus eines Falls:
          1. Fall anlegen → DRAFT
          2. Dokument hochladen → pending OCR
          3. Dokumente auflisten → 1 Dokument
          4. Status prüfen → 'processing'
          5. OCR simulieren → completed
          6. Status prüfen → 'completed'
          7. Analyse starten → 202
          8. Dokument löschen
          9. Fall löschen
          10. Fallliste leer
        """
        mock_storage_factory.return_value = _mock_storage()
        client, _ = auth_client

        # 1. Fall anlegen
        case_id = client.post("/api/v1/cases").json()["case_id"]
        assert client.get("/api/v1/cases").json()["cases"][0]["status"] == "DRAFT"

        # 2. Dokument hochladen
        doc_data = client.post(
            f"/api/v1/cases/{case_id}/documents",
            files=[_pdf("vertrag.pdf")]
        ).json()
        doc_id = doc_data["document_id"]
        assert doc_data["ocr_status"] == "pending"

        # 3. Dokumente auflisten
        docs = client.get(f"/api/v1/cases/{case_id}/documents").json()["documents"]
        assert len(docs) == 1
        assert docs[0]["filename"] == "vertrag.pdf"

        # 4. Status → 'processing' (Dokument noch pending)
        status = client.get(f"/api/v1/cases/{case_id}/status").json()
        assert status["status"] == "processing"

        # 5. OCR in DB abschließen (simuliert Worker-Ergebnis)
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        doc_obj = db.query(Document).filter(Document.id == uuid.UUID(doc_id)).first()
        doc_obj.ocr_status = "completed"
        doc_obj.masked_text = "Rechnung vom 01.01.2024 über € 274,50"
        db.commit()

        # 6. Status → 'completed'
        status = client.get(f"/api/v1/cases/{case_id}/status").json()
        assert status["status"] == "completed"
        assert status["completed"] == 1
        assert status["preview"] is not None

        # 7. Analyse starten → 202
        res = client.post(f"/api/v1/cases/{case_id}/analyze")
        assert res.status_code == 202

        # 8. Dokument löschen
        with patch("app.api.v1.documents.get_storage") as ms:
            ms.return_value = _mock_storage()
            res = client.delete(f"/api/v1/cases/{case_id}/documents/{doc_id}")
        assert res.status_code == 200
        assert client.get(f"/api/v1/cases/{case_id}/documents").json()["documents"] == []

        # 9. Fall löschen
        with patch("app.api.v1.cases.get_storage") as ms:
            ms.return_value = _mock_storage()
            res = client.delete(f"/api/v1/cases/{case_id}")
        assert res.status_code == 200

        # 10. Fallliste leer
        assert client.get("/api/v1/cases").json()["cases"] == []

    @patch("app.api.v1.documents.get_storage")
    @patch("app.workers.ocr_worker.run_ocr")
    def test_reupload_after_delete_works(self, mock_ocr, mock_storage_factory, auth_client, db):
        """
        Nach dem Löschen eines Dokuments kann ein neues hochgeladen werden.
        (Regression: Input-Reset-Bug im Frontend)
        """
        mock_storage_factory.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()

        # Hochladen
        first_doc_id = client.post(
            f"/api/v1/cases/{case_id}/documents", files=[_pdf("first.pdf")]
        ).json()["document_id"]

        # Löschen
        with patch("app.api.v1.documents.get_storage") as ms:
            ms.return_value = _mock_storage()
            client.delete(f"/api/v1/cases/{case_id}/documents/{first_doc_id}")

        # Erneut hochladen (darf nicht fehlschlagen)
        res = client.post(f"/api/v1/cases/{case_id}/documents", files=[_pdf("second.pdf")])
        assert res.status_code == 201
        docs = client.get(f"/api/v1/cases/{case_id}/documents").json()["documents"]
        assert len(docs) == 1
        assert docs[0]["filename"] == "second.pdf"

    def test_two_users_cases_fully_isolated(self, auth_client, db):
        """
        Zwei Nutzer können Fälle anlegen – keiner sieht die Fälle des anderen.
        """
        client_a, _ = auth_client

        # Nutzer A legt Fall an
        case_a_id = client_a.post("/api/v1/cases").json()["case_id"]

        # Nutzer B anlegen und einloggen
        from app.main import app as fastapi_app
        from fastapi.testclient import TestClient
        from app.core.security import create_access_token

        user_b = User(
            email="userB@example.com",
            hashed_password=hash_password("passwortB123"),
            accepted_terms=True,
        )
        db.add(user_b)
        db.commit()
        db.refresh(user_b)

        client_b = TestClient(fastapi_app)
        token_b = create_access_token(str(user_b.id))
        client_b.cookies.set("access_token", token_b)

        # Nutzer B legt eigenen Fall an
        case_b_id = client_b.post("/api/v1/cases").json()["case_id"]

        # Gegenseitige Isolation prüfen
        cases_a = [c["case_id"] for c in client_a.get("/api/v1/cases").json()["cases"]]
        cases_b = [c["case_id"] for c in client_b.get("/api/v1/cases").json()["cases"]]

        assert case_a_id in cases_a
        assert case_b_id not in cases_a
        assert case_b_id in cases_b
        assert case_a_id not in cases_b
