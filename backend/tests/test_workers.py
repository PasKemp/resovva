"""
Deep Integration Tests for Asynchronous Workers.

Verifies the end-to-end logic of the OCR and Dossier workers, 
including database state transitions and business logic side effects.
External APIs are mocked via the mock_external_apis fixture.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch, MagicMock

import pytest

from app.workers.ocr_worker import run_ocr
from app.workers.dossier_worker import run_dossier_generation
from app.domain.models.db import Case, Document, User


# ── OCR Worker ───────────────────────────────────────────────────────────────

class TestOCRWorkerDeep:
    """Verifies process_document logic (app/services/extraction/pipeline.py)."""

    @patch("app.services.extraction.pipeline.extract_text_local")
    @patch("app.services.extraction.pipeline.mask_pii")
    def test_run_ocr_success_flow(self, mock_mask, mock_local, db, mock_external_apis):
        """Should transition document status from pending to completed."""
        # 1. Setup
        user = User(email="worker@example.com", hashed_password="pw", accepted_terms=True)
        db.add(user)
        db.commit()
        
        case = Case(user_id=user.id, status="DRAFT")
        db.add(case)
        db.commit()
        
        doc = Document(
            case_id=case.id,
            filename="invoice.pdf",
            s3_key="key/inv.pdf",
            ocr_status="pending"
        )
        db.add(doc)
        db.commit()
        
        # 2. Mocks
        mock_local.return_value = MagicMock(text="Raw Text", page_count=1)
        mock_mask.return_value = "Masked Text"
        
        # 3. Execution (Calling the worker logic directly)
        run_ocr(str(doc.id))
        
        # 4. Verification
        db.refresh(doc)
        assert doc.ocr_status == "completed"
        assert doc.masked_text == "Masked Text"
        assert mock_mask.called
        assert mock_external_apis["rag"].called # Should trigger embedding


# ── Dossier Worker ───────────────────────────────────────────────────────────

class TestDossierWorkerDeep:
    """Verifies run_dossier_generation logic (app/workers/dossier_worker.py)."""

    @patch("app.services.dossier_generator.DossierGenerator.generate")
    @patch("app.services.evidence_compiler.EvidenceCompiler.compile")
    def test_run_dossier_success_flow(self, mock_compile, mock_generate, db, mock_external_apis):
        """Should transition case status from GENERATING to COMPLETED."""
        # 1. Setup
        user = User(
            email="dossier@example.com", 
            hashed_password="pw", 
            accepted_terms=True,
            first_name="John",
            last_name="Doe"
        )
        db.add(user)
        db.commit()
        
        case = Case(user_id=user.id, status="TIMELINE_READY")
        db.add(case)
        db.commit()
        
        # 2. Mocks
        mock_generate.return_value = b"PDF-CONTENT"
        mock_compile.return_value = "s3/path/to/dossier.pdf"
        
        # 3. Execution
        run_dossier_generation(str(case.id))
        
        # 4. Verification
        db.refresh(case)
        assert case.status == "COMPLETED"
        assert case.extracted_data["dossier_s3_key"] == "s3/path/to/dossier.pdf"
        assert mock_external_apis["resend"].called # Email should be sent
