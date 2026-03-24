"""
RAG-Modul – Chunking, Embedding und Vektorsuche (US-3.1 / US-3.2).

Öffentliche API:
  chunk_and_embed(document_id, case_id, text)  → Chunks einbetten & in Qdrant speichern
  search_rag(query, case_id, limit)            → Semantische Suche für Entity-Extraktion

Qdrant-Unavailability-safe: alle Operationen kehren still zurück, ohne Exception.
"""

from __future__ import annotations

import logging
from typing import List

from app.infrastructure.azure_openai import embed_texts
from app.infrastructure.qdrant_client import upsert_documents, search_similar

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1000     # Zeichen pro Chunk (US-3.1: max 1000)
CHUNK_OVERLAP = 100   # Überlapp für Kontextkontinuität


# ── Chunking ───────────────────────────────────────────────────────────────────


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    """
    Teilt Text in überlappende Chunks auf (US-3.1).

    Verwendet LangChain RecursiveCharacterTextSplitter falls verfügbar,
    sonst einfaches Sliding-Window als Fallback.
    """
    if not text.strip():
        return []
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", ".", " ", ""],
        )
        return splitter.split_text(text)
    except ImportError:
        chunks, start = [], 0
        while start < len(text):
            chunks.append(text[start : start + chunk_size])
            start += chunk_size - overlap
        return chunks


# ── Embedding & Storage ────────────────────────────────────────────────────────


def chunk_and_embed(document_id: str, case_id: str, text: str) -> int:
    """
    Zerlegt den maskierten Text in Chunks, bettet sie ein und speichert sie in Qdrant.

    Wird nach erfolgreichem PII-Masking in der Extraction-Pipeline aufgerufen.
    Schlägt still fehl wenn Qdrant oder OpenAI-Key nicht konfiguriert.

    Args:
        document_id: UUID des Dokuments (in Qdrant-Payload gespeichert).
        case_id:     UUID des Falls (für case-gefilterte RAG-Suche).
        text:        PII-maskierter Dokumenttext.

    Returns:
        Anzahl gespeicherter Chunks (0 falls unavailable).
    """
    from app.core.config import get_settings

    chunks = chunk_text(text)
    if not chunks:
        return 0

    embeddings = embed_texts(chunks)
    if not embeddings:
        logger.warning(
            "Embedding fehlgeschlagen – kein API-Key? Dokument %s nicht eingebettet.", document_id
        )
        return 0

    settings = get_settings()
    ids = [f"{document_id}__chunk_{i}" for i in range(len(chunks))]
    payloads = [
        {
            "case_id": case_id,
            "document_id": document_id,
            "chunk_index": i,
            "text": chunk,
        }
        for i, chunk in enumerate(chunks)
    ]
    upsert_documents(
        collection=settings.qdrant_collection,
        ids=ids,
        embeddings=embeddings,
        payloads=payloads,
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
    )
    logger.info("RAG: %d Chunks für Dokument %s eingebettet.", len(chunks), document_id)
    return len(chunks)


# ── Retrieval ──────────────────────────────────────────────────────────────────


def search_rag(query: str, case_id: str, limit: int = 5) -> List[str]:
    """
    Semantische Suche in den eingebetteten Dokumenten eines Falls (US-3.2).

    Args:
        query:   Suchbegriff (z.B. "Zählernummer Stromzähler").
        case_id: Filtert Ergebnisse auf diesen Fall.
        limit:   Maximale Anzahl Treffer.

    Returns:
        Liste relevanter Textpassagen – leer wenn Qdrant unavailable.
    """
    from app.core.config import get_settings

    query_embs = embed_texts([query])
    if not query_embs:
        return []

    settings = get_settings()
    results = search_similar(
        collection=settings.qdrant_collection,
        query_embedding=query_embs[0],
        limit=limit,
        case_id=case_id,
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
    )
    return [r["text"] for r in results]
