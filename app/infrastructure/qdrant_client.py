"""
Vektor-DB Wrapper – Qdrant.

Embeddings speichern/abfragen für RAG auf User-Dokumenten.
"""

from typing import List, Optional

# from qdrant_client import QdrantClient
# from qdrant_client.models import Distance, VectorParams, PointStruct


def get_qdrant_client(url: str = "http://localhost:6333", api_key: Optional[str] = None):
    """
    Factory für Qdrant-Client.
    TODO: Aus app.core.config lesen, Collection anlegen falls nicht vorhanden.
    """
    # return QdrantClient(url=url, api_key=api_key)
    return None


def upsert_documents(
    collection: str,
    ids: List[str],
    embeddings: List[List[float]],
    payloads: List[dict],
):
    """Dokumente (mit Embeddings) in Qdrant upserten."""
    # TODO: QdrantClient.upsert(collection_name=collection, points=[...])
    pass


def search_similar(
    collection: str,
    query_embedding: List[float],
    limit: int = 10,
) -> List[dict]:
    """Ähnlichkeitssuche in der Collection."""
    # TODO: QdrantClient.search(...)
    return []
