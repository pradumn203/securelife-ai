"""Async database engine, session factory, and schema bootstrap."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.settings import get_settings


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    """SQLAlchemy `connect` hook: turn on FK enforcement for this connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class Database:
    """Owns the async engine and session factory.

    One instance per process (constructed in `main.lifespan`). Session-per-job
    pattern: anyone doing background work opens a fresh session via `session()`
    instead of reusing a request-scoped one. See ARCHITECTURE.md §7.1.
    """

    def __init__(self, url: str) -> None:
        self._engine: AsyncEngine = create_async_engine(
            url,
            echo=False,
            future=True,
            pool_pre_ping=True,
        )
        if self._engine.url.get_backend_name().startswith("sqlite"):
            # `PRAGMA foreign_keys` is per-connection in SQLite, so it must run
            # on every pooled connection — not once at startup.
            event.listen(self._engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )

    async def create_all(self) -> None:
        """Create all tables (dev-time). Alembic would replace this in prod."""
        from app.data_models import Base  # imported lazily so metadata is complete

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def enable_sqlite_wal(self) -> None:
        """Enable WAL for SQLite to reduce 'database is locked' under concurrency.

        WAL is persisted in the database file, so once at startup is enough.
        """
        from sqlalchemy import text

        if not self._engine.url.get_backend_name().startswith("sqlite"):
            return
        async with self._engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL;"))

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Open a session scoped to this context. Caller owns the transaction."""
        async with self._session_factory() as session:
            yield session

    async def dispose(self) -> None:
        await self._engine.dispose()


_db: Database | None = None


def get_db() -> Database:
    """Return the process-wide Database. Must be initialized by `init_db`."""
    global _db
    if _db is None:
        raise RuntimeError("Database not initialized; call init_db() first.")
    return _db


async def init_db() -> Database:
    """Initialize the database and create tables."""
    global _db
    if _db is None:
        _db = Database(get_settings().database_url)
        await _db.enable_sqlite_wal()
        await _db.create_all()
    return _db


async def shutdown_db() -> None:
    """Dispose the global engine (used on app shutdown)."""
    global _db
    if _db is not None:
        await _db.dispose()
        _db = None


async def session_dependency() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a request-scoped session."""
    async with get_db().session() as session:
        yield session
