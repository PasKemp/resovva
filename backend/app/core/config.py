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
    app_name: str = "Resovva.de"
    debug: bool = False

    # Database (PostgreSQL – Hauptdatenbank)
    database_url: Optional[str] = None

    # JWT / Session
    secret_key: str = "change-me-in-production-use-a-random-256bit-key"
    jwt_expire_days: int = 7

    # CORS – erlaubte Frontend-Origins (komma-getrennt)
    allowed_origins: str = "http://localhost:5173"

    # E-Mail (Resend – Passwort-Reset)
    resend_api_key: Optional[str] = None
    email_from: str = "noreply@resovva.de"

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

    # S3 / MinIO Storage (Epic 2)
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "resovva-docs"

    # Stripe (Epic 5 – Checkout / Payments)
    stripe_secret_key: Optional[str] = None       # sk_live_... or sk_test_...
    stripe_webhook_secret: Optional[str] = None   # whsec_...
    stripe_price_id: Optional[str] = None         # price_...  (€20 pro Fall)
    app_base_url: str = "http://localhost:5173"   # Redirect-URLs nach Checkout

    # Privacy
    data_retention_days: int = 30

    # Text-Extraktion Pipeline (Epic 8)
    llama_cloud_api_key: Optional[str] = None   # LlamaParse Cloud API Key
    min_chars_per_page: int = 50                # Fallback-Schwelle für pypdf (MIN_CHARS_PER_PAGE)


@lru_cache
def get_settings() -> Settings:
    return Settings()
