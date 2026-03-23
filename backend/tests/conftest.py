"""
Pytest-Fixtures für EPIC1-Tests.

Test-DB: resovva_test (PostgreSQL, wird beim ersten Testlauf auto-erstellt).
Tabellen werden pro Test erstellt und danach gelöscht – sauberer Zustand.

Voraussetzung: PostgreSQL erreichbar (docker-compose up reicht).
  Standard-URL: postgresql://postgres:postgres@localhost:5432/resovva_test
  Überschreibbar via Umgebungsvariable: TEST_DATABASE_URL

Ausführen:
  cd backend && pytest tests/ -v
"""

import os
import re

# ── Umgebungsvariablen vor dem App-Import setzen ──────────────────────────────
# get_settings() verwendet lru_cache – muss VOR dem ersten Import gesetzt sein.

_default_test_db = "postgresql://resovva:password@localhost:5432/resovva_test"
os.environ["DATABASE_URL"]     = os.environ.get("TEST_DATABASE_URL", _default_test_db)
os.environ.setdefault("SECRET_KEY",       "test-secret-key-nur-fuer-tests-niemals-in-prod")
os.environ.setdefault("ALLOWED_ORIGINS",  "http://localhost:5173")

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

import app.infrastructure.database as _db_module
from app.domain.models.db import Base, User
from app.infrastructure.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app


# ── Session-Fixtures: einmalig pro Test-Lauf ──────────────────────────────────


@pytest.fixture(scope="session")
def ensure_test_db():
    """
    Erstellt die Test-Datenbank falls sie nicht existiert.
    Überspringe alle DB-Tests wenn PostgreSQL nicht erreichbar ist.
    """
    db_url  = os.environ["DATABASE_URL"]
    db_name = db_url.split("/")[-1]
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
        pytest.skip(f"PostgreSQL nicht erreichbar – DB-Tests übersprungen: {exc}")


@pytest.fixture(scope="session")
def test_engine(ensure_test_db):
    """SQLAlchemy-Engine gegen die Test-DB (einmal pro Session erstellt)."""
    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    # In database-Modul injizieren, damit get_db die Test-DB nutzt
    _db_module._engine       = engine
    _db_module._SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    yield engine
    engine.dispose()


# ── Dependency Override ───────────────────────────────────────────────────────


def _override_get_db():
    db = _db_module._SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


# ── Funktions-Fixtures: einmal pro Test ───────────────────────────────────────


@pytest.fixture
def reset_db(test_engine):
    """Erstellt alle Tabellen vor dem Test, löscht sie danach (isolierter Zustand)."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db(reset_db):
    """Direkte DB-Session – für Setup-Code in Tests (Objekte vorab anlegen)."""
    session = _db_module._SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(reset_db):
    """
    Nicht authentifizierter HTTP-Testclient mit sauberer Datenbank.
    Hängt von reset_db ab → Tabellen werden vor/nach jedem Test zurückgesetzt.
    Rate-Limiter wird vor jedem Test zurückgesetzt (Brute-Force-Schutz teilt
    sonst denselben "testclient"-IP-Schlüssel über alle Tests).
    """
    try:
        from app.core.limiter import limiter
        limiter._storage.reset()
    except Exception:
        pass
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def test_user(db) -> User:
    """Legt einen Testnutzer direkt in der DB an (kein HTTP-Roundtrip)."""
    user = User(
        email="test@example.com",
        hashed_password=hash_password("sicheresPasswort123"),
        accepted_terms=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_client(client, test_user):
    """
    TestClient mit gesetztem JWT-Cookie für den Testnutzer.
    Gibt (client, user) zurück.
    """
    token = create_access_token(str(test_user.id))
    client.cookies.set("access_token", token)
    return client, test_user
