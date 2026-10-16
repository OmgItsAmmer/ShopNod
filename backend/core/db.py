"""Async SQLAlchemy engine/session. Works on Postgres (prod) and SQLite (tests, quick local)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .settings import get_settings

_engine: AsyncEngine | None = None
_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _maker
    if _engine is None:
        url = get_settings().DATABASE_URL
        kwargs: dict = {} if url.startswith("sqlite") else {"pool_pre_ping": True}
        _engine = create_async_engine(url, **kwargs)
        _tune_sqlite(_engine)
        _maker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def _tune_sqlite(engine: AsyncEngine) -> None:
    """SQLite (tests / quick local runs): WAL + a busy timeout so concurrent writers wait instead of failing."""
    if engine.dialect.name != "sqlite":
        return
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _pragmas(dbapi_conn, _):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA foreign_keys=OFF")
        cur.close()


def get_maker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _maker is not None
    return _maker


async def dispose_engine() -> None:
    global _engine, _maker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _maker = None


def configure_engine(engine: AsyncEngine) -> None:
    """Used by tests to inject an engine."""
    global _engine, _maker
    _engine = engine
    _tune_sqlite(engine)
    _maker = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Transactional scope: commit on success, roll back on error."""
    async with get_maker()() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Commits at the end of the request if no exception."""
    async with session_scope() as s:
        yield s


# `scope="function"`: commit BEFORE the response is sent, so a client that immediately re-reads sees its write.
DB = Depends(get_session, scope="function")
