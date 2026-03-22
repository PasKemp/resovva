"""
SQLAlchemy Session Factory.

Stellt eine synchrone DB-Session via FastAPI Depends() bereit.
Erwartet DATABASE_URL in den Umgebungsvariablen (z.B. postgresql://user:pass@host/db).
"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine = None
_SessionLocal = None


def _get_engine():
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


def create_all_tables() -> None:
    """
    Erstellt alle Tabellen direkt via SQLAlchemy (für Tests / lokale Entwicklung).
    In Production: Alembic-Migrationen nutzen.
    """
    from app.domain.models.db import Base
    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
