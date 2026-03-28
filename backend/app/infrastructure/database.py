"""
SQLAlchemy database infrastructure.

Provides the database engine, session factory, and dependency injection
helpers for both FastAPI requests and background tasks.
"""

import logging
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Singletons for engine and session factory
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker[Session]] = None


def _get_engine() -> Engine:
    """
    Get the SQLAlchemy engine singleton.

    Creates the engine if it doesn't exist. URL is retrieved from settings.

    Returns:
        Engine: The initialized SQLAlchemy engine.

    Raises:
        RuntimeError: If DATABASE_URL is not configured.
    """
    global _engine, _SessionLocal
    if _engine is None:
        url = get_settings().database_url
        if not url:
            raise RuntimeError(
                "DATABASE_URL is not configured. Please set the environment variable."
            )
        _engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _engine


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency: provides a transactional database session.

    Yields:
        Session: A SQLAlchemy database session.
    """
    _get_engine()  # Ensure engine is initialized
    db: Session = _SessionLocal()  # type: ignore[misc]
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions used outside of FastAPI requests.

    Yields:
        Session: A SQLAlchemy database session.
    """
    _get_engine()
    db: Session = _SessionLocal()  # type: ignore[misc]
    try:
        yield db
    finally:
        db.close()


def create_all_tables() -> None:
    """
    Initialize database schema and run idempotent column migrations.

    Should be called on application startup.
    """
    from app.domain.models.db import Base
    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
    _run_column_migrations(engine)


def _run_column_migrations(engine: Engine) -> None:
    """
    Add missing columns to existing tables (idempotent).

    Args:
        engine: The SQLAlchemy engine to use for migrations.
    """
    migrations = [
        # Epic 2: OCR Status
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS ocr_status  VARCHAR(20)  NOT NULL DEFAULT 'pending'",
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS masked_text TEXT",
        # Epic 9: Opponent Model
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS opponent_category VARCHAR(50)",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS opponent_name    VARCHAR(255)",
        # Epic 7: Case Brief initial context
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS initial_context JSONB",
    ]

    with engine.begin() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                logger.debug("Migration executed: %s", sql[:60])
            except Exception as exc:
                logger.warning(
                    "Migration skipped or failed: %s", sql[:60],
                    extra={"error": str(exc)}
                )
