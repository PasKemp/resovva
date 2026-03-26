"""
Vektor-DB Wrapper – Qdrant (US-3.1).

Embeddings speichern/abfragen für RAG auf User-Dokumenten.
Collection: resovva_docs  |  Vektor-Dimension: 1536 (text-embedding-3-small)

Alle öffentlichen Funktionen sind Qdrant-unavailability-safe:
  – Client nicht erreichbar → Log-Warning, kein Exception-Propagation.
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional

logger = logging.getLogger(__name__)

# Lazy Singleton – wird beim ersten get_qdrant_client()-Aufruf initialisiert.
_client = None


def get_qdrant_client(
    url: str = "http://localhost:6333",
    api_key: Optional[str] = None,
):
    """
    Liefert einen (gecachten) Qdrant-Client.

    Returns:
        QdrantClient oder None wenn Qdrant nicht erreichbar.
    """
    global _client
    if _client is not None:
        return _client
    try:
        from qdrant_client import QdrantClient

        _client = QdrantClient(url=url, api_key=api_key or None, timeout=10)
        logger.info("Qdrant-Client verbunden: %s", url)
    except Exception as exc:
        logger.warning("Qdrant nicht erreichbar (%s): %s – RAG deaktiviert.", url, exc)
        return None
    return _client


def ensure_collection(
    client,
    collection: str,
    vector_size: int = 1536,
) -> None:
    """Erstellt die Qdrant-Collection falls sie noch nicht existiert."""
    from qdrant_client.models import Distance, VectorParams

    existing = {c.name for c in client.get_collections().collections}
    if collection not in existing:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        logger.info("Qdrant-Collection '%s' angelegt (dim=%d).", collection, vector_size)


def upsert_documents(
    collection: str,
    ids: List[str],
    embeddings: List[List[float]],
    payloads: List[dict],
    url: str = "http://localhost:6333",
    api_key: Optional[str] = None,
) -> None:
    """
    Speichert Dokument-Chunks mit Embeddings in Qdrant.

    Jeder Punkt bekommt eine deterministische UUID aus der chunk-ID
    (uuid5 über NAMESPACE_URL), sodass Re-Embedding idempotent ist.
    """
    from qdrant_client.models import PointStruct

    client = get_qdrant_client(url, api_key)
    if client is None or not embeddings:
        return

    vector_size = len(embeddings[0])
    try:
        ensure_collection(client, collection, vector_size=vector_size)
        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id)),
                vector=emb,
                payload=payload,
            )
            for chunk_id, emb, payload in zip(ids, embeddings, payloads)
        ]
        client.upsert(collection_name=collection, points=points)
        logger.debug("Qdrant: %d Punkte in '%s' gespeichert.", len(points), collection)
    except Exception as exc:
        logger.warning("Qdrant upsert fehlgeschlagen: %s", exc)


def search_similar(
    collection: str,
    query_embedding: List[float],
    limit: int = 5,
    case_id: Optional[str] = None,
    url: str = "http://localhost:6333",
    api_key: Optional[str] = None,
) -> List[dict]:
    """
    Vektorsuche in der Collection, optional nach case_id gefiltert.

    Nutzt query_points() (qdrant-client ≥ 1.7, ersetzt das veraltete search()).

    Returns:
        Liste von {"text": str, "score": float} – leer wenn Qdrant unavailable.
    """
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    client = get_qdrant_client(url, api_key)
    if client is None:
        return []

    query_filter = None
    if case_id:
        query_filter = Filter(
            must=[FieldCondition(key="case_id", match=MatchValue(value=case_id))]
        )
    try:
        response = client.query_points(
            collection_name=collection,
            query=query_embedding,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )
        return [
            {
                "text": p.payload.get("text", ""),
                "score": p.score,
                "document_id": p.payload.get("document_id"),
            }
            for p in response.points
        ]
    except Exception as exc:
        logger.warning("Qdrant-Suche fehlgeschlagen: %s", exc)
        return []


def delete_by_case(
    collection: str,
    case_id: str,
    url: str = "http://localhost:6333",
    api_key: Optional[str] = None,
) -> None:
    """Löscht alle Vektoren eines Falls (DSGVO Hard-Delete)."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    client = get_qdrant_client(url, api_key)
    if client is None:
        return
    try:
        client.delete(
            collection_name=collection,
            points_selector=Filter(
                must=[FieldCondition(key="case_id", match=MatchValue(value=case_id))]
            ),
        )
        logger.info("Qdrant: Alle Vektoren für Case %s gelöscht.", case_id)
    except Exception as exc:
        logger.warning("Qdrant delete_by_case fehlgeschlagen (Case %s): %s", case_id, exc)
