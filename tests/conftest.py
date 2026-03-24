"""Shared test fixtures for DJ Music Plugin.

All fixtures use async SQLAlchemy with in-memory SQLite.
"""

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.audio import (  # noqa: F401
    Embedding,
    FeatureExtractionRun,
    TimeseriesReference,
    TrackAudioFeaturesComputed,
    TrackSection,
)
from app.models.base import Base
from app.models.key import Key, KeyEdge  # noqa: F401
from app.models.library import (  # noqa: F401
    DjBeatgrid,
    DjBeatgridChangePoint,
    DjCuePoint,
    DjLibraryItem,
    DjSavedLoop,
)
from app.models.playlist import Playlist, PlaylistItem  # noqa: F401
from app.models.set import DjSet, SetConstraint, SetFeedback, SetItem, SetVersion  # noqa: F401
from app.models.track import Track  # noqa: F401
from app.models.transition import Transition, TransitionCandidate  # noqa: F401


def _set_sqlite_pragma(dbapi_conn, _connection_record):
    """Enable FK enforcement for SQLite connections."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
async def async_engine():
    """In-memory async SQLite engine with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    event.listen(engine.sync_engine, "connect", _set_sqlite_pragma)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(async_engine) -> AsyncSession:  # type: ignore[no-untyped-def]
    """Async session that rolls back after each test."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def seeded_db(db):  # type: ignore[no-untyped-def]
    """Session with reference data: 24 Camelot keys."""
    from app.core.constants import CAMELOT_KEYS

    # Lazy import — models may not exist yet during early tasks
    try:
        from app.models.key import Key

        for code, (camelot, name) in CAMELOT_KEYS.items():
            mode = 1 if camelot.endswith("B") else 0
            pitch_class = code % 12
            db.add(
                Key(
                    key_code=code,
                    pitch_class=pitch_class,
                    mode=mode,
                    name=name,
                    camelot=camelot,
                )
            )
        await db.flush()
    except ImportError:
        pass  # Key model not yet created

    yield db


# ── MCP Client fixtures ──────────────────────────────


def _parse_tool_result(result):  # type: ignore[no-untyped-def]
    """Extract dict from MCP CallToolResult."""
    import json as _json

    if hasattr(result, "data") and isinstance(result.data, dict):
        return result.data
    content = getattr(result, "content", result)
    if isinstance(content, list) and len(content) > 0:
        block = content[0]
        text = getattr(block, "text", None) or str(block)
        return _json.loads(text)
    if isinstance(result, dict):
        return result
    raise ValueError(f"Unexpected result type: {type(result)}")


@pytest.fixture
async def client(async_engine):  # type: ignore[no-untyped-def]
    """FastMCP test client with in-memory DB session factory."""
    from fastmcp import Client
    from fastmcp.server.lifespan import Lifespan
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.server import mcp

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    original_lifespan = mcp._lifespan

    async def _test_lifespan(server):  # type: ignore[no-untyped-def]
        yield {"db_engine": async_engine, "db_session_factory": factory}

    mcp._lifespan = Lifespan(_test_lifespan)

    try:
        async with Client(mcp) as c:
            yield c
    finally:
        mcp._lifespan = original_lifespan
