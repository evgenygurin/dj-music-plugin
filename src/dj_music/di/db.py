"""Database-scoped dependency factories."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import import_module

from sqlalchemy.ext.asyncio import AsyncSession


def _get_context():  # type: ignore[no-untyped-def]
    dependencies = import_module("dj_music.di")
    return dependencies.get_context()


@asynccontextmanager
async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Scoped async DB session — auto-commit on success, rollback on error."""
    ctx = _get_context()
    factory = ctx.lifespan_context["db_session_factory"]
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
