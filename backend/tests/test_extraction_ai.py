"""
AI Analysis & Extraction Engine Integration Tests.

Covers US-3.1 (RAG: Chunking, Embedding, Vector Search), 
US-3.2 (Entity Extraction), US-3.3 (Early Exit),
US-3.4 (MaStR-Lookup & RAG Fallback), and US-3.5 (HiTL).
External dependencies like Qdrant, OpenAI, and MaStR API are mocked.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── US-3.1: RAG – Chunking ───────────────────────────────────────────────────

class TestChunkText:
    """Verifies that chunk_text splits text correctly for embedding."""

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
        assert all(len(c) > 0 for c in chunks)


# ── US-3.1: RAG – chunk_and_embed (Mocked Integration) ───────────────────────

class TestChunkAndEmbed:
    """Verifies coordination between chunking, embedding, and vector storage."""

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


# ── US-3.2: Extraction Routing ───────────────────────────────────────────────

class TestCheckMissingData:
    """Verifies conditional routing based on extracted entity completeness."""

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


# ── US-3.4: MaStR-Lookup ─────────────────────────────────────────────────────

class TestMastrLookup:
    """Verifies external MaStR API interaction."""

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
        mock_client_cls.return_value = mock_client

        result = await _lookup_mastr("DE01234567890123")
        assert result == "Stadtwerke München"


# ── US-3.4: RAG-Fallback for Operator Identification ─────────────────────────

class TestRagFallback:
    """Verifies that RAG is used if MaStR lookup fails."""

    @pytest.mark.asyncio
    @patch("app.agents.nodes.mastr_lookup.search_rag", return_value=["Netzbetreiber Stadtwerke Berlin GmbH"])
    async def test_extracts_operator_keyword(self, _mock_rag):
        from app.agents.nodes.mastr_lookup import _rag_fallback
        result = await _rag_fallback("case-xyz")
        assert result is not None
        assert "Stadtwerke" in result
