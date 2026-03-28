"""
Application configuration management using Pydantic Settings.

This module loads environment variables from a .env file and provides a
type-safe way to access application settings.
"""

from functools import lru_cache
from typing import Optional

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Global application settings.

    Attributes:
        app_name: Name of the application.
        debug: Enable/disable debug mode.
        database_url: Connection string for the PostgreSQL database.
        secret_key: Secret key for JWT signing and sessions.
        jwt_expire_days: Token validity duration in days.
        allowed_origins: CORS origins allowed to access the API.
        resend_api_key: API key for Resend email service.
        email_from: Sender email address for system notifications.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    app_name: str = "Resovva.de"
    debug: bool = False

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: Optional[str] = None

    # ── Auth & Security ───────────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:5173"

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_changed(cls, v: str, info) -> str:
        """
        Fail-fast check for production readiness.
        
        Ensures the default development secret is not used in production.
        """
        if not info.data.get("debug") and v == "change-me-in-production-use-a-random-256bit-key":
            raise ValueError(
                "SECRET_KEY must be a random, secure string in production. "
                "Update your .env file or environment variables."
            )
        return v

    # ── Email (Resend) ────────────────────────────────────────────────────────
    resend_api_key: Optional[str] = None
    email_from: str = "noreply@resovva.de"

    # ── LLM (OpenAI / Azure) ──────────────────────────────────────────────────
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_deployment: str = "gpt-4o"
    openai_api_version: str = "2024-02-15-preview"
    openai_api_key: Optional[str] = None

    # ── Embeddings ────────────────────────────────────────────────────────────
    embedding_model: str = "text-embedding-3-small"
    embedding_deployment: Optional[str] = None

    # ── Qdrant ────────────────────────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection: str = "resovva_docs"

    # ── LangGraph ─────────────────────────────────────────────────────────────
    postgres_checkpoint_url: Optional[str] = None

    # ── External APIs ─────────────────────────────────────────────────────────
    mastr_api_base_url: str = "https://api.marktstammdatenregister.de"

    # ── Ingest & Document Processing ──────────────────────────────────────────
    ingest_backend: str = "text"
    azure_document_intelligence_endpoint: Optional[str] = None
    azure_document_intelligence_key: Optional[str] = None
    llama_cloud_api_key: Optional[str] = None
    min_chars_per_page: int = 50

    # ── S3 / MinIO Storage ────────────────────────────────────────────────────
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "resovva-docs"
    s3_public_url: Optional[str] = None

    # ── Stripe (Payments) ─────────────────────────────────────────────────────
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    stripe_price_id: Optional[str] = None
    app_base_url: str = "http://localhost:5173"

    # ── Privacy & Retention ───────────────────────────────────────────────────
    data_retention_days: int = 30


@lru_cache
def get_settings() -> Settings:
    """
    Get application settings singleton.

    Returns:
        Settings: The cached settings instance.
    """
    return Settings()
