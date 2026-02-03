"""
Pydantic Settings – Env Vars.

Liest Konfiguration aus Umgebungsvariablen (z.B. .env).
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "Resovva.ai"
    debug: bool = False

    # Azure OpenAI (DSGVO: Azure Germany) – für Production
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_deployment: str = "gpt-4o"
    openai_api_version: str = "2024-02-15-preview"

    # Standard OpenAI (platform.openai.com) – für DEV ohne Azure-Genehmigung
    openai_api_key: Optional[str] = None

    # Embeddings
    embedding_model: str = "text-embedding-3-small"
    embedding_deployment: Optional[str] = None

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection: str = "resovva_docs"

    # LangGraph Checkpointer (Postgres für Persistenz; leer = MemorySaver)
    postgres_checkpoint_url: Optional[str] = None

    # MaStR-API (Marktstammdatenregister)
    mastr_api_base_url: str = "https://api.marktstammdatenregister.de"

    # RAG/Ingest: Backend für PDF+Tabellen (text | unstructured | azure)
    ingest_backend: str = "text"
    # Azure Document Intelligence (wenn ingest_backend=azure)
    azure_document_intelligence_endpoint: Optional[str] = None
    azure_document_intelligence_key: Optional[str] = None

    # Privacy
    data_retention_days: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
