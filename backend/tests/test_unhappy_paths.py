"""
Unhappy Path Integration Tests for Workers.

Verifies that asynchronous workers gracefully handle failures (network errors, 
resource missing) and persist error details in the database.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from app.workers.ocr_worker import run_ocr
from app.workers.dossier_worker import run_dossier_generation
from app.domain.models.db import Case, Document, User


class TestWorkerUnhappyPaths:
    """Error handling verification."""

    @patch("app.services.extraction.pipeline.extract_text_local")
    def test_run_ocr_fails_when_storage_offline(self, mock_local, db, mock_external_apis):
        """Should transition document status to 'error' if S3 download fails."""
        # 1. Setup
        user = User(email="fail1@example.com", hashed_password="pw", accepted_terms=True)
        db.add(user)
        db.commit()
        
        case = Case(user_id=user.id, status="DRAFT")
        db.add(case)
        db.commit()
        
        doc = Document(
            case_id=case.id,
            filename="crash.pdf",
            s3_key="key/crash.pdf",
            ocr_status="pending"
        )
        db.add(doc)
        db.commit()
        
        # 2. Mock storage to raise exception
        mock_external_apis["storage"].download_file.side_effect = Exception("S3 timeout")
        
        # 3. Execution
        run_ocr(str(doc.id))
        
        # 4. Verification
        db.refresh(doc)
        assert doc.ocr_status == "error"


    def test_run_dossier_fails_gracefully(self, db, mock_external_apis):
        """Should transition case status to 'ERROR_GENERATION' if something crashes."""
        # 1. Setup
        user = User(email="fail2@example.com", hashed_password="pw", accepted_terms=True)
        db.add(user)
        db.commit()
        
        case = Case(user_id=user.id, status="TIMELINE_READY")
        db.add(case)
        db.commit()
        
        # 2. Mock missing data or crash during generation (mocking generator at low level)
        with patch("app.services.dossier_generator.DossierGenerator.generate") as mock_gen:
            mock_gen.side_effect = RuntimeError("Generation logic crashed")
            
            # 3. Execution
            run_dossier_generation(str(case.id))
            
        # 4. Verification
        db.refresh(case)
        assert case.status == "ERROR_GENERATION"
        assert "Generation logic crashed" in case.extracted_data["error_log"]["message"]
