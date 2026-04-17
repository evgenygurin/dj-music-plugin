"""Shared test fixtures for DJ Music Plugin.

All fixtures use async SQLAlchemy with in-memory SQLite.
"""

import contextlib
import os

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models.audio import (  # noqa: F401
    Embedding,
    FeatureExtractionRun,
    TimeseriesReference,
    TrackAudioFeaturesComputed,
    TrackSection,
)
from app.db.models.base import Base
from app.db.models.export import AppExport  # noqa: F401
from app.db.models.ingestion import ProviderModel, RawProviderResponse  # noqa: F401
from app.db.models.key import Key, KeyEdge  # noqa: F401
from app.db.models.library import (  # noqa: F401
    DjBeatgrid,
    DjBeatgridChangePoint,
    DjCuePoint,
    DjLibraryItem,
    DjSavedLoop,
)
from app.db.models.platform import YandexMetadata  # noqa: F401
from app.db.models.playlist import Playlist, PlaylistItem  # noqa: F401
from app.db.models.scoring_profile import ScoringProfile  # noqa: F401
from app.db.models.set import DjSet, SetConstraint, SetFeedback, SetItem, SetVersion  # noqa: F401
from app.db.models.track import Track, TrackExternalId  # noqa: F401
from app.db.models.track_affinity import TrackAffinity  # noqa: F401
from app.db.models.track_feedback import TrackFeedback  # noqa: F401
from app.db.models.transition import Transition, TransitionCandidate  # noqa: F401
from app.db.models.transition_history import TransitionHistory  # noqa: F401


def pytest_xdist_auto_num_workers(config):  # type: ignore[no-untyped-def]
    """Cap xdist auto workers to avoid CPU over-subscription in audio-heavy tests.

    `-n auto` can pick too many workers for this suite because many tests execute
    NumPy/librosa workloads internally. Fewer workers reduce context switching and
    consistently improve wall-clock time.
    """
    configured = config.getoption("numprocesses")
    if configured != "auto":
        return None
    return min(4, max(1, os.cpu_count() or 1))


def pytest_collection_modifyitems(config, items):  # type: ignore[no-untyped-def]
    """Group audio tests on one worker to avoid numba/librosa cold-start races.

    When many workers import/compile librosa+numba in parallel on a cold cache,
    workers can crash and xdist spends significant time restarting nodes.
    `loadgroup` + a shared group keeps these tests on one worker while the rest
    of the suite still runs in parallel.
    """
    if config.getoption("dist") != "loadgroup":
        return
    for item in items:
        if item.nodeid.startswith("tests/test_audio/"):
            item.add_marker(pytest.mark.xdist_group(name="audio"))


def _set_sqlite_pragma(dbapi_conn, _connection_record):
    """Enable FK enforcement for SQLite connections."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(scope="session")
async def async_engine():
    """Session-wide in-memory async SQLite engine.

    Creates schema once per xdist worker, then test-level cleanup fixture
    resets table contents between tests.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    event.listen(engine.sync_engine, "connect", _set_sqlite_pragma)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _reset_database(async_engine, request):  # type: ignore[no-untyped-def]
    """Clear DB rows only for tests that actually use DB-bound fixtures.

    This keeps isolation for DB tests while avoiding expensive table cleanup
    work for pure unit tests that never touch SQLAlchemy.
    """
    db_fixtures = {"db", "seeded_db", "client", "acceptance_harness", "async_engine"}
    if db_fixtures.isdisjoint(set(request.fixturenames)):
        yield
        return

    async with async_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
        with contextlib.suppress(Exception):
            await conn.exec_driver_sql("DELETE FROM sqlite_sequence")
    yield


@pytest.fixture(scope="session")
def analyzer_registry():  # type: ignore[no-untyped-def]
    """Discovered analyzer registry reused across tests."""
    from app.audio.analyzers import AnalyzerRegistry

    registry = AnalyzerRegistry()
    registry.discover()
    return registry


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
        from app.db.models.key import Key

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
async def client(async_engine, analyzer_registry):  # type: ignore[no-untyped-def]
    """FastMCP test client with in-memory DB session factory."""
    from fastmcp import Client
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.server import mcp

    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    original_lifespan = mcp._lifespan

    from unittest.mock import AsyncMock

    from app.core.utils.cache import TransitionCache

    # Provide all lifespan context keys that tools may need
    registry = analyzer_registry
    cache = TransitionCache(max_size=100, ttl=60)

    # Mock YM client
    ym_mock = AsyncMock()
    ym_mock.__aenter__.return_value = ym_mock
    ym_mock.__aexit__.return_value = None
    ym_mock.search = AsyncMock(
        return_value=AsyncMock(tracks=[], albums=[], artists=[], playlists=[])
    )
    ym_mock.get_liked_ids = AsyncMock(return_value=[])
    ym_mock.get_disliked_ids = AsyncMock(return_value=set())

    # Mock ProviderRegistry (required after multi-provider refactor)
    from unittest.mock import MagicMock

    from app.core.constants import Provider
    from app.providers.registry import ProviderRegistry

    provider_mock = MagicMock()
    provider_mock.provider = Provider.YANDEX_MUSIC
    provider_registry = ProviderRegistry()
    provider_registry.register(provider_mock, default=True)

    from fastmcp.server.lifespan import lifespan

    @lifespan
    async def _test_lifespan(server):  # type: ignore[no-untyped-def]
        yield {
            "db_engine": async_engine,
            "db_session_factory": factory,
            "ym_client": ym_mock,
            "analyzer_registry": registry,
            "transition_cache": cache,
            "provider_registry": provider_registry,
        }

    mcp._lifespan = _test_lifespan
    mcp._lifespan_result = None
    mcp._lifespan_result_set = False

    try:
        async with Client(mcp) as c:
            yield c
    finally:
        # Reset cached lifespan result so next test gets a fresh lifespan
        mcp._lifespan_result = None
        mcp._lifespan_result_set = False
        mcp._lifespan = original_lifespan
