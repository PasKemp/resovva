"""
Pytest Fixtures and Configuration.

Target database: resovva_test (PostgreSQL).
The test database is automatically created if it doesn't exist.
Tables are recreated per test to ensure clean state and isolation.

Requirements:
- PostgreSQL must be reachable (e.g., via docker-compose).
- Default URL: postgresql://resovva:password@localhost:5432/resovva_test
- Overridable via TEST_DATABASE_URL environment variable.
"""

from __future__ import annotations

import os
import re
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

import app.infrastructure.database as _db_module
from app.domain.models.db import Base, User
from app.infrastructure.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app


# ── Environment Configuration ───────────────────────────────────────────────

# Ensure environment variables are set BEFORE app imports settings (lru_cache)
_default_test_db = "postgresql://resovva:password@localhost:5432/resovva_test"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", _default_test_db)
os.environ.setdefault("SECRET_KEY", "test-secret-key-only-for-tests-never-use-in-prod")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:5173")


# ── Session Fixtures (Run once per session) ──────────────────────────────────

@pytest.fixture(scope="session")
def ensure_test_db():
    """
    Creates the test database if it is missing.
    Skips all DB-related tests if PostgreSQL is unreachable.
    """
    db_url = os.environ["DATABASE_URL"]
    db_name = db_url.split("/")[-1]
    # Replace DB name in URL with 'postgres' for admin connection
    admin_url = re.sub(r"/[^/]+$", "/postgres", db_url)

    try:
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            ).fetchone()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
        admin_engine.dispose()
    except Exception as exc:
        pytest.skip(f"PostgreSQL unreachable – skipping DB tests: {exc}")


@pytest.fixture(scope="session")
def test_engine(ensure_test_db):
    """SQLAlchemy engine for the test database."""
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    # Inject into database module so get_db uses the test engine
    _db_module._engine = engine
    _db_module._SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    yield engine
    engine.dispose()


# ── Dependency Overrides ─────────────────────────────────────────────────────

def _override_get_db():
    """FastAPI dependency override for database sessions."""
    db = _db_module._SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


# ── Function Fixtures (Run once per test) ────────────────────────────────────

@pytest.fixture
def reset_db(test_engine):
    """Creates all tables before a test and drops them afterwards for isolation."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db(reset_db):
    """Direct database session for setup code within tests."""
    session = _db_module._SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(reset_db):
    """
    Unauthenticated HTTP test client with a clean database.
    Depends on reset_db to ensure table state isolation.
    Resets the rate limiter for consistent behavior across tests.
    """
    try:
        from app.core.limiter import limiter
        limiter._storage.reset()
    except Exception:
        pass
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def test_user(db) -> User:
    """Creates a test user directly in the database (no HTTP roundtrip)."""
    user = User(
        email="test@example.com",
        hashed_password=hash_password("SecurePassword123"),
        accepted_terms=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_client(client, test_user):
    """
    TestClient with a valid JWT session cookie for the test user.
    Returns a tuple of (client, user).
    """
    token = create_access_token(str(test_user.id))
    client.cookies.set("access_token", token)
    return client, test_user


@pytest.fixture
def mock_external_apis():
    """
    Centrally mocks all external service dependencies.
    Prevents accidental real API calls to Stripe, Resend (Email), and S3.
    """
    with (
        patch("app.infrastructure.storage.get_storage") as mock_storage,
        patch("app.services.extraction.pipeline.get_storage") as mock_pipeline_storage,
        patch("resend.Emails.send") as mock_resend,
        patch("stripe.checkout.Session.create") as mock_stripe,
        patch("app.core.rag.chunk_and_embed") as mock_rag,
    ):
        # Mock S3 behavior
        storage_instance = MagicMock()
        storage_instance.upload_file.return_value = "mocked/key"
        storage_instance.download_file.return_value = b"%PDF-1.4"
        mock_storage.return_value = storage_instance
        mock_pipeline_storage.return_value = storage_instance
        
        # Mock Stripe
        mock_stripe.return_value = MagicMock(id="cs_test", url="https://stripe.com/test")
        
        yield {
            "storage": storage_instance,
            "resend":  mock_resend,
            "stripe":  mock_stripe,
            "rag":     mock_rag,
        }
