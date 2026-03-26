"""
SQLAlchemy Session Factory.

Stellt eine synchrone DB-Session via FastAPI Depends() bereit.
Erwartet DATABASE_URL in den Umgebungsvariablen (z.B. postgresql://user:pass@host/db).
"""

# stdlib
import logging
from contextlib import contextmanager
from typing import Generator

# third-party
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# local
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


def _get_engine() -> Engine:
    """Lazy-Singleton für die DB-Engine (einmal pro Prozess erstellt)."""
    global _engine, _SessionLocal
    if _engine is None:
        url = get_settings().database_url
        if not url:
            raise RuntimeError(
                "DATABASE_URL ist nicht konfiguriert. "
                "Setze die Umgebungsvariable DATABASE_URL."
            )
        _engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _engine


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI-Dependency: liefert eine SQLAlchemy-Session und schließt sie danach.

    Usage:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    _get_engine()  # Stellt sicher, dass Engine initialisiert ist
    db: Session = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context-Manager für DB-Sessions außerhalb von FastAPI-Requests.
    Genutzt von Background-Tasks (z.B. OCR-Worker).

    Usage:
        with get_db_context() as db:
            ...
    """
    _get_engine()
    db: Session = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables() -> None:
    """
    Erstellt alle Tabellen und führt Schema-Migrationen aus.

    create_all() erstellt nur fehlende Tabellen – vorhandene werden nicht
    verändert. Für neue Spalten in bestehenden Tabellen nutzen wir
    `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (idempotent, PostgreSQL 9.6+).

    In Production mit echten DB-Releases: Alembic-Migrationen einsetzen.
    """
    from app.domain.models.db import Base
    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
    _run_column_migrations(engine)


def _run_column_migrations(engine: Engine) -> None:
    """
    Fügt fehlende Spalten zu bestehenden Tabellen hinzu (idempotent).
    Wird bei jedem App-Start ausgeführt – keine Aktion wenn Spalte existiert.
    """
    migrations = [
        # Epic 2 (US-2.4 & US-2.5): OCR-Status und maskierter Text in documents
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS ocr_status  VARCHAR(20)  NOT NULL DEFAULT 'pending'",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS masked_text TEXT",
        # Epic 9 (US-9.1): Generisches Streitparteien-Modell
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS opponent_category VARCHAR(50)",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS opponent_name    VARCHAR(255)",
    ]
    with engine.begin() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                logger.debug("Migration ausgeführt: %s", sql[:60])
            except Exception as exc:
                logger.warning("Migration übersprungen (%s): %s", sql[:60], exc)
