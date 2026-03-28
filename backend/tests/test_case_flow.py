"""
Full Integration Tests – Case Lifecycle.

Covers US-1.4 (List), US-1.6 (Create), US-1.7 (GDPR Delete),
and US-2.2 (Document Upload).
Verifies the complete flow from case initiation to document processing.
"""

from __future__ import annotations

import io
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.security import hash_password
from app.domain.models.db import Case, Document, User


# ── Test Data Helpers ────────────────────────────────────────────────────────

# Minimal valid magic bytes for file format validation
_PDF_MAGIC  = b"%PDF-1.4 minimal"
_JPEG_MAGIC = b"\xFF\xD8\xFF\xE0" + b"\x00" * 20
_PNG_MAGIC  = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
_INVALID    = b"NOTAFILE" + b"\x00" * 20


def _pdf(name: str = "inv.pdf") -> tuple[str, tuple]:
    """Helper to generate a mock PDF file."""
    return ("file", (name, io.BytesIO(_PDF_MAGIC), "application/pdf"))


def _jpeg(name: str = "photo.jpg") -> tuple[str, tuple]:
    """Helper to generate a mock JPEG file."""
    return ("file", (name, io.BytesIO(_JPEG_MAGIC), "image/jpeg"))


def _mock_storage():
    """Returns a storage service mock simulating S3 interactions."""
    mock = MagicMock()
    mock.upload_file.return_value = None
    mock.delete_file.return_value = None
    return mock


def _create_second_user_with_case(db) -> tuple[User, Case]:
    """Sets up a secondary user/case to verify tenant isolation."""
    other = User(
        email="other@example.com",
        password=hash_password("pw123"),
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


def _create_doc_in_db(db, case: Case, ocr_status: str = "pending") -> Document:
    """Helper to insert a document directly into the database."""
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


# ── Case Lifecycle Tests ─────────────────────────────────────────────────────

class TestCaseFlow:
    """End-to-end flow from creation to analysis."""

    def test_create_case_success(self, auth_client):
        """Standard case creation should return 201 Created."""
        client, _ = auth_client
        res = client.post("/api/v1/cases")
        assert res.status_code == 201
        assert "case_id" in res.json()

    def test_list_cases_shows_metadata(self, auth_client):
        """Case list should return all essential case attributes."""
        client, _ = auth_client
        client.post("/api/v1/cases")
        res = client.get("/api/v1/cases")
        assert res.status_code == 200
        case = res.json()["cases"][0]
        assert all(k in case for k in ("case_id", "status", "document_count"))

    def test_case_status_updates_with_docs(self, auth_client, db):
        """Case status endpoint should correctly reflect OCR progress."""
        client, user = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        _create_doc_in_db(db, case, ocr_status="completed")

        res = client.get(f"/api/v1/cases/{case_id}/status")
        assert res.json()["status"] == "completed"
        assert res.json()["total"] == 1


class TestDocumentFlow:
    """Document upload and management lifecycle."""

    @patch("app.api.v1.documents.get_storage")
    @patch("app.workers.ocr_worker.run_ocr")
    def test_upload_and_list_document(self, mock_ocr, mock_storage, auth_client, db):
        """Uploading a document should make it appear in the listing."""
        mock_storage.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        
        # Upload
        upload_res = client.post(f"/api/v1/cases/{case_id}/documents", files=[_pdf()])
        assert upload_res.status_code == 201
        doc_id = upload_res.json()["document_id"]

        # List
        list_res = client.get(f"/api/v1/cases/{case_id}/documents")
        docs = list_res.json()["documents"]
        assert any(d["document_id"] == doc_id for d in docs)

    @patch("app.api.v1.documents.get_storage")
    def test_delete_document_success(self, mock_storage, auth_client, db):
        """Deleting a document should remove it from listing (HTTP 200)."""
        mock_storage.return_value = _mock_storage()
        client, _ = auth_client
        case_id = client.post("/api/v1/cases").json()["case_id"]
        case = db.query(Case).filter(Case.id == uuid.UUID(case_id)).first()
        doc = _create_doc_in_db(db, case)

        res = client.delete(f"/api/v1/cases/{case_id}/documents/{doc.id}")
        assert res.status_code == 200
        
        # Verify removal
        list_res = client.get(f"/api/v1/cases/{case_id}/documents")
        assert not any(d["document_id"] == str(doc.id) for d in list_res.json()["documents"])


class TestSecurityAndIsolation:
    """Verifies that user data cannot be accessed across account boundaries."""

    def test_cannot_access_other_users_case(self, auth_client, db):
        """Any attempt to access a foreign case_id should return 404."""
        client, _ = auth_client
        _, foreign_case = _create_second_user_with_case(db)
        
        status_res = client.get(f"/api/v1/cases/{foreign_case.id}/status")
        assert status_res.status_code == 404

        delete_res = client.delete(f"/api/v1/cases/{foreign_case.id}")
        assert delete_res.status_code == 404
