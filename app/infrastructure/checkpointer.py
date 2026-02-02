"""
LangGraph Checkpointer – MemorySaver oder PostgresSaver.

Wenn POSTGRES_CHECKPOINT_URL gesetzt ist und [postgres] installiert:
  pip install resovva[postgres]
  → PostgresSaver mit Connection-Pool, Persistenz über Prozess/Server-Restarts.
Sonst: MemorySaver (nur In-Memory, für Dev).
"""

from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from app.core.config import get_settings


_checkpointer: Any = None


def get_checkpointer():
    """Liefert den konfigurierten Checkpointer (einmalig erstellt, dann wiederverwendet)."""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    settings = get_settings()
    if not settings.postgres_checkpoint_url:
        _checkpointer = MemorySaver()
        return _checkpointer

    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
    except ImportError:
        _checkpointer = MemorySaver()
        return _checkpointer

    pool = ConnectionPool(
        conninfo=settings.postgres_checkpoint_url,
        kwargs={"autocommit": True, "row_factory": dict_row},
    )
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    _checkpointer = checkpointer
    return _checkpointer
