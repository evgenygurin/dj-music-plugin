"""Shared fixtures for v2 tests.

Provides:
- ``engine``: function-scoped aiosqlite in-memory engine
- ``session``: function-scoped AsyncSession with rollback

Both are wired for SQLAlchemy 2.0 async. In tests that use the ORM, the
module should define its own declarative Base + models (or import them).
The fixture creates all tables belonging to whatever Base it is given via
the ``create_tables`` helper.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


@pytest_asyncio.fixture(scope="function")
async def engine() -> AsyncIterator[AsyncEngine]:
    """Fresh in-memory SQLite engine per test."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        try:
            yield s
        finally:
            await s.rollback()


@pytest.fixture
def create_tables() -> Callable[[type[DeclarativeBase], AsyncEngine], AsyncIterator[None]]:
    """Helper returning an async context manager for creating tables per-Base."""

    async def _create(base: type[DeclarativeBase], eng: AsyncEngine) -> None:
        async with eng.begin() as conn:
            await conn.run_sync(base.metadata.create_all)

    return _create  # type: ignore[return-value]
