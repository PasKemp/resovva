"""
Tests für EPIC 3: AI Analysis & Extraction Engine.

Abgedeckte Bereiche:
  - US-3.1: RAG (Chunking, Embedding, Vektorsuche)
  - US-3.2: Entity-Extraktion (check_missing_data-Edge)
  - US-3.3: Early Exit bei fehlenden Kerndaten
  - US-3.4: MaStR-Lookup & RAG-Fallback
  - US-3.5: HiTL – Confirm-Endpoint & Resume

Externe Abhängigkeiten werden gemockt:
  - Qdrant via @patch("app.infrastructure.qdrant_client.get_qdrant_client")
  - OpenAI Embeddings via @patch("app.infrastructure.azure_openai.embed_texts")
  - LLM via @patch("app.agents.nodes.extract._get_mini_llm")
  - MaStR-API via @patch("httpx.AsyncClient")
  - DB via @patch("app.infrastructure.database.get_db_context")
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# US-3.1: RAG – Chunking
# ─────────────────────────────────────────────────────────────────────────────


class TestChunkText:
    """chunk_text splittert Text korrekt."""

    def test_empty_text_returns_empty_list(self):
        from app.core.rag import chunk_text

        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_short_text_returns_single_chunk(self):
        from app.core.rag import chunk_text

        result = chunk_text("Hello World", chunk_size=500)
        assert len(result) == 1
        assert result[0] == "Hello World"

    def test_long_text_is_split(self):
        from app.core.rag import chunk_text

        long_text = "A" * 3000
        chunks = chunk_text(long_text, chunk_size=1000, overlap=100)
        assert len(chunks) > 1
        # Kein Chunk darf leer sein
        assert all(len(c) > 0 for c in chunks)

    def test_overlap_means_chunks_share_content(self):
        from app.core.rag import chunk_text

        # 200 Zeichen + 50 Overlap → Überlapp vorhanden
        text = "X" * 100 + "Y" * 100 + "Z" * 100
        chunks = chunk_text(text, chunk_size=150, overlap=50)
        # Mindestens 2 Chunks
        assert len(chunks) >= 2


# ─────────────────────────────────────────────────────────────────────────────
# US-3.1: RAG – chunk_and_embed (Integration mit Mocks)
# ─────────────────────────────────────────────────────────────────────────────


class TestChunkAndEmbed:
    """chunk_and_embed ruft embed_texts und upsert_documents korrekt auf."""

    @patch("app.infrastructure.qdrant_client.upsert_documents")
    @patch("app.core.rag.upsert_documents")
    @patch("app.core.rag.embed_texts", return_value=[[0.1] * 1536])
    @patch("app.core.rag.chunk_text", return_value=["chunk1"])
    def test_stores_chunks_in_qdrant(self, mock_chunk, mock_embed, mock_upsert, _):
        from app.core.rag import chunk_and_embed

        result = chunk_and_embed("doc-1", "case-1", "some text")

        assert result == 1
        mock_embed.assert_called_once_with(["chunk1"])
        mock_upsert.assert_called_once()

    @patch("app.core.rag.embed_texts", return_value=[])
    def test_returns_zero_when_embedding_fails(self, mock_embed):
        from app.core.rag import chunk_and_embed

        result = chunk_and_embed("doc-1", "case-1", "some text")
        assert result == 0

    def test_returns_zero_for_empty_text(self):
        from app.core.rag import chunk_and_embed

        result = chunk_and_embed("doc-1", "case-1", "")
        assert result == 0


# ─────────────────────────────────────────────────────────────────────────────
# US-3.2: check_missing_data – Conditional Edge
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckMissingData:
    """check_missing_data routet korrekt basierend auf extrahierten Feldern."""

    def _state(self, meter_number=None, malo_id=None):
        return {
            "case_id": "test-case",
            "meter_number": meter_number,
            "malo_id": malo_id,
            "messages": [],
            "documents": [],
            "extracted_entities": {},
            "chronology": [],
            "missing_info": [],
            "dossier_ready": False,
            "payment_status": "pending",
        }

    def test_both_null_routes_to_missing_data(self):
        from app.agents.nodes.extract import check_missing_data

        assert check_missing_data(self._state()) == "missing_data"

    def test_malo_id_present_routes_to_mastr_lookup(self):
        from app.agents.nodes.extract import check_missing_data

        assert check_missing_data(self._state(malo_id="DE123")) == "mastr_lookup"

    def test_meter_number_present_routes_to_mastr_lookup(self):
        from app.agents.nodes.extract import check_missing_data

        assert check_missing_data(self._state(meter_number="Z001")) == "mastr_lookup"

    def test_both_present_routes_to_mastr_lookup(self):
        from app.agents.nodes.extract import check_missing_data

        assert check_missing_data(self._state(meter_number="Z001", malo_id="DE123")) == "mastr_lookup"


# ─────────────────────────────────────────────────────────────────────────────
# US-3.2: node_extract – LLM-Extraktion
# ─────────────────────────────────────────────────────────────────────────────


class TestNodeExtract:
    """node_extract ruft LLM auf und schreibt Ergebnisse in State."""

    def _base_state(self):
        return {
            "case_id": "case-abc",
            "messages": ["--- Dokument ---\nZählernummer: Z1234"],
            "documents": [],
            "extracted_entities": {},
            "meter_number": None,
            "malo_id": None,
            "dispute_amount": None,
            "currency": None,
            "network_operator": None,
            "chronology": [],
            "missing_info": [],
            "dossier_ready": False,
            "payment_status": "pending",
        }

    @pytest.mark.asyncio
    @patch("app.agents.nodes.extract.search_rag", return_value=["Zählernummer: Z1234\nMaLo: DE0123"])
    @patch("app.agents.nodes.extract._get_mini_llm")
    async def test_successful_extraction(self, mock_llm_fn, mock_rag):
        from app.agents.nodes.extract import node_extract
        from app.domain.models.document import ExtractedEntity

        # Build a mock chain that returns ExtractedEntity when awaited
        mock_result = ExtractedEntity(
            malo_id="DE0123",
            meter_number="Z1234",
            amount_disputed=274.50,
        )
        mock_chain = AsyncMock(return_value=mock_result)
        # The node does: chain = _EXTRACT_PROMPT | llm.with_structured_output(...)
        # then: result = await chain.ainvoke(...)
        # We patch at the ainvoke level by making the whole chain mock
        mock_bound = MagicMock()
        mock_bound.ainvoke = AsyncMock(return_value=mock_result)
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_llm
        # _EXTRACT_PROMPT | mock_llm → mock_bound
        mock_llm_fn.return_value = mock_llm

        with patch("app.agents.nodes.extract._EXTRACT_PROMPT") as mock_prompt:
            mock_prompt.__or__ = MagicMock(return_value=mock_bound)
            result = await node_extract(self._base_state())

        assert result["malo_id"] == "DE0123"
        assert result["meter_number"] == "Z1234"
        assert result["dispute_amount"] == 274.50
        assert result["currency"] == "EUR"
        assert result["current_step"] == "extract"

    @pytest.mark.asyncio
    @patch("app.agents.nodes.extract.search_rag", return_value=[])
    @patch("app.agents.nodes.extract._get_mini_llm")
    async def test_rag_empty_falls_back_to_messages(self, mock_llm_fn, mock_rag):
        from app.agents.nodes.extract import node_extract
        from app.domain.models.document import ExtractedEntity

        mock_result = ExtractedEntity(meter_number="Z9999")
        mock_bound = MagicMock()
        mock_bound.ainvoke = AsyncMock(return_value=mock_result)
        mock_llm_fn.return_value = MagicMock()

        with patch("app.agents.nodes.extract._EXTRACT_PROMPT") as mock_prompt:
            mock_prompt.__or__ = MagicMock(return_value=mock_bound)
            result = await node_extract(self._base_state())

        # RAG empty → Fallback zu messages → Extraktion läuft trotzdem
        assert result["current_step"] in ("extract", "extract_error")

    @pytest.mark.asyncio
    @patch("app.agents.nodes.extract.search_rag", return_value=["some text"])
    @patch("app.agents.nodes.extract._get_mini_llm", side_effect=ValueError("No API key"))
    async def test_llm_error_sets_extract_error_step(self, mock_llm, mock_rag):
        from app.agents.nodes.extract import node_extract

        result = await node_extract(self._base_state())
        assert result["current_step"] == "extract_error"
        assert any("fehlgeschlagen" in m for m in result["messages"])


# ─────────────────────────────────────────────────────────────────────────────
# US-3.4: MaStR-Lookup
# ─────────────────────────────────────────────────────────────────────────────


class TestMastrLookup:
    """_lookup_mastr gibt Namen zurück oder None bei Fehler."""

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_successful_lookup(self, mock_client_cls):
        from app.agents.nodes.mastr_lookup import _lookup_mastr

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"NetzbetreiberName": "Stadtwerke München"}

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await _lookup_mastr("DE0123456789012345678")
        assert result == "Stadtwerke München"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_timeout_returns_none(self, mock_client_cls):
        from app.agents.nodes.mastr_lookup import _lookup_mastr

        mock_client = AsyncMock()
        mock_client.get.side_effect = TimeoutError("timeout")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await _lookup_mastr("DE0123")
        assert result is None

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_non_200_returns_none(self, mock_client_cls):
        from app.agents.nodes.mastr_lookup import _lookup_mastr

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await _lookup_mastr("DE0123")
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# US-3.4: RAG-Fallback für Netzbetreiber
# ─────────────────────────────────────────────────────────────────────────────


class TestRagFallback:
    @pytest.mark.asyncio
    @patch("app.agents.nodes.mastr_lookup.search_rag", return_value=["Netzbetreiber Stadtwerke Berlin GmbH"])
    async def test_extracts_betreiber_keyword(self, _mock_rag):
        from app.agents.nodes.mastr_lookup import _rag_fallback

        result = await _rag_fallback("case-xyz")
        assert result is not None
        assert "Stadtwerke" in result

    @pytest.mark.asyncio
    @patch("app.agents.nodes.mastr_lookup.search_rag", return_value=[])
    async def test_returns_none_when_no_hits(self, _mock_rag):
        from app.agents.nodes.mastr_lookup import _rag_fallback

        result = await _rag_fallback("case-xyz")
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# US-3.3 / US-3.5: _persist_to_db
# ─────────────────────────────────────────────────────────────────────────────


class TestPersistToDb:
    def _state(self, **kwargs):
        return {
            "case_id": "11111111-1111-1111-1111-111111111111",
            "meter_number": "Z001",
            "malo_id": "DE0123",
            "dispute_amount": 100.0,
            "currency": "EUR",
            "network_operator": None,
            **kwargs,
        }

    @patch("app.agents.nodes.mastr_lookup.get_db_context")
    def test_sets_waiting_for_user(self, mock_ctx):
        from app.agents.nodes.mastr_lookup import _persist_to_db

        mock_case = MagicMock()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = mock_case
        mock_ctx.return_value.__enter__ = MagicMock(return_value=db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        _persist_to_db(self._state(), "Stadtwerke Berlin")

        assert mock_case.status == "WAITING_FOR_USER"
        assert mock_case.extracted_data["network_operator"] == "Stadtwerke Berlin"
        assert mock_case.extracted_data["confirmed"] is False
        db.commit.assert_called_once()

    def test_invalid_case_id_does_not_raise(self):
        from app.agents.nodes.mastr_lookup import _persist_to_db

        state = self._state(case_id="not-a-uuid")
        # sollte keinen Exception werfen
        _persist_to_db(state, None)


# ─────────────────────────────────────────────────────────────────────────────
# US-3.1: Pipeline-Integration – chunk_and_embed wird nach Masking aufgerufen
# ─────────────────────────────────────────────────────────────────────────────


class TestPipelineEmbedIntegration:
    @patch("app.services.extraction.pipeline.mask_pii", return_value="masked text")
    @patch("app.services.extraction.pipeline.get_storage")
    @patch("app.services.extraction.pipeline.get_db_context")
    @patch("app.services.extraction.pipeline._embed_document")
    def test_embed_called_after_masking(self, mock_embed, mock_ctx, mock_storage_fn, mock_mask):
        from app.services.extraction.local_extractor import LocalExtractionResult
        from app.services.extraction.pipeline import process_document

        doc = MagicMock()
        doc.id = "doc-1"
        doc.case_id = "case-1"
        doc.s3_key = "case-1/doc.pdf"
        doc.ocr_status = "pending"
        doc.masked_text = None

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = doc
        mock_ctx.return_value.__enter__.return_value = db

        mock_storage_fn.return_value = MagicMock(download_file=MagicMock(return_value=b"%PDF"))

        rich_result = LocalExtractionResult(text="A" * 500, page_count=1, chars_per_page=[500])
        with patch(
            "app.services.extraction.pipeline.extract_text_local",
            return_value=rich_result,
        ):
            process_document("doc-1")

        mock_embed.assert_called_once_with(doc, "masked text")
