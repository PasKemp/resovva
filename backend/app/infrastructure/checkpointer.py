"""
LangGraph Checkpointer – MemorySaver (Dev/Tests) oder AsyncPostgresSaver (Prod).

  PostgresSaver (sync)   → aput/aget/... raise NotImplementedError  ❌
  AsyncPostgresSaver     → async-safe, muss im Event-Loop erstellt werden ✅

AsyncPostgresSaver.__init__ ruft asyncio.get_running_loop() auf, daher
muss es aus einem async-Kontext erstellt werden.

Öffentliche API:
  get_sync_checkpointer()    → MemorySaver (für Tests & Graph-Import ohne Loop)
  create_async_checkpointer() → AsyncPostgresSaver | MemorySaver (async context)
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_sync_checkpointer() -> MemorySaver:
    """
    Gibt immer einen MemorySaver zurück (synchron, kein Event-Loop nötig).

    Wird für Tests und Nicht-Async-Kontexte genutzt.
    """
    return MemorySaver()


async def create_async_checkpointer() -> Any:
    """
    Erstellt den Checkpointer für den async Graph-Lauf.

    - POSTGRES_CHECKPOINT_URL gesetzt + psycopg_pool installiert
      → AsyncPostgresSaver (persistenter State, interrupt/resume über Prozess-Restarts)
    - Sonst → MemorySaver (in-process, ausreichend für single-worker Dev/Docker)

    Muss aus einem async-Kontext aufgerufen werden (Event-Loop muss laufen).

    Returns:
        AsyncPostgresSaver | MemorySaver
    """
    settings = get_settings()

    if not settings.postgres_checkpoint_url:
        logger.info("Checkpointer: MemorySaver (kein POSTGRES_CHECKPOINT_URL).")
        return MemorySaver()

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg_pool import AsyncConnectionPool
    except ImportError:
        logger.warning(
            "psycopg_pool oder langgraph-checkpoint-postgres nicht installiert "
            "– Fallback auf MemorySaver."
        )
        return MemorySaver()

    pool = AsyncConnectionPool(
        conninfo=settings.postgres_checkpoint_url,
        kwargs={"autocommit": True},
        min_size=1,
        max_size=5,
        open=False,
    )
    await pool.open()

    saver = AsyncPostgresSaver(pool)
    await saver.setup()  # Checkpoint-Tabellen anlegen (idempotent)

    logger.info("Checkpointer: AsyncPostgresSaver bereit (async-safe).")
    return saver
