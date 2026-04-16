"""Acceptance tests for the declarative draft set flow."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult
from fastmcp.server.lifespan import lifespan
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.audio.analyzers import AnalyzerRegistry
from app.core.constants import Provider
from app.core.utils.cache import TransitionCache
from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.track import Track
from app.db.repositories.set import SetRepository
from app.providers.registry import ProviderRegistry
from app.server import mcp
from tests.acceptance.conftest import parse_tool_result


def _read_draft_resource(result) -> dict:  # type: ignore[no-untyped-def]
    item = result[0] if result else None
    text = getattr(item, "text", None) or "{}"
    return json.loads(text) if isinstance(text, str) else {}


def _build_lifespan(async_engine, factory):  # type: ignore[no-untyped-def]
    registry = AnalyzerRegistry()
    registry.discover()
    cache = TransitionCache(max_size=100, ttl=60)
    ym_mock = AsyncMock()
    ym_mock.__aenter__.return_value = ym_mock
    ym_mock.__aexit__.return_value = None
    provider_mock = MagicMock()
    provider_mock.provider = Provider.YANDEX_MUSIC
    provider_registry = ProviderRegistry()
    provider_registry.register(provider_mock, default=True)

    @lifespan
    async def _ls(server):  # type: ignore[no-untyped-def]
        yield {
            "db_engine": async_engine,
            "db_session_factory": factory,
            "ym_client": ym_mock,
            "analyzer_registry": registry,
            "transition_cache": cache,
            "provider_registry": provider_registry,
        }

    return _ls


@pytest.mark.asyncio
async def test_full_draft_flow_creates_ordered_version(
    async_engine,
    patch_tiered_noop,
) -> None:
    """update_set_draft → preview_draft → update_set_draft → commit_draft (accept)."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)

    track_ids: list[int] = []
    async with factory() as session:
        for i in range(4):
            t = Track(title=f"Draft Flow Track {i}", status=0, duration_ms=180000)
            session.add(t)
            await session.flush()
            track_ids.append(t.id)
            session.add(
                TrackAudioFeaturesComputed(
                    track_id=t.id,
                    bpm=130.0 + i,
                    key_code=8 + i,
                    integrated_lufs=-11.0,
                    energy_mean=0.6 + i * 0.03,
                    spectral_centroid_hz=2400.0,
                    onset_rate=4.0,
                    kick_prominence=0.6,
                )
            )
        await session.commit()

    async def accept_handler(request):  # type: ignore[return]
        return ElicitResult(action="accept", content=None)

    original_lifespan = mcp._lifespan
    mcp._lifespan = _build_lifespan(async_engine, factory)
    mcp._lifespan_result = None
    mcp._lifespan_result_set = False

    try:
        async with Client(mcp, elicitation_handler=accept_handler) as c:
            # 1. Set initial draft
            await c.call_tool(
                "update_set_draft",
                {
                    "track_ids": track_ids,
                    "name": "Draft Flow Set",
                    "template": None,
                },
            )

            # 2. Preview — fast mode
            preview1 = parse_tool_result(await c.call_tool("preview_draft", {"narrative": False}))
            assert "score" in preview1
            assert preview1["track_count"] == 4

            # 3. Refine: reverse the order
            reversed_ids = list(reversed(track_ids))
            await c.call_tool("update_set_draft", {"track_ids": reversed_ids})

            # 4. Preview again
            preview2 = parse_tool_result(await c.call_tool("preview_draft", {}))
            assert preview2["track_count"] == 4

            # 5. Commit — elicitation auto-accepts
            commit_data = parse_tool_result(
                await c.call_tool(
                    "commit_draft",
                    {
                        "version_label": "v1-acceptance",
                    },
                )
            )
            assert commit_data["set_id"] > 0
            assert commit_data["track_count"] == 4
            assert commit_data["version_label"] == "v1-acceptance"

        # Verify DB: version exists with reversed track order
        async with factory() as session:
            repo = SetRepository(session)
            version = await repo.get_latest_version(commit_data["set_id"])
            assert version is not None
            items = await repo.get_version_items(version.id)
            assert [item.track_id for item in items] == reversed_ids
    finally:
        mcp._lifespan_result = None
        mcp._lifespan_result_set = False
        mcp._lifespan = original_lifespan


@pytest.mark.asyncio
async def test_session_state_isolation(async_engine, patch_tiered_noop) -> None:
    """Session A's draft must NOT be visible in Session B (opened after A closes)."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)

    original_lifespan = mcp._lifespan
    mcp._lifespan = _build_lifespan(async_engine, factory)
    mcp._lifespan_result = None
    mcp._lifespan_result_set = False
    try:
        # Session A: set a draft
        async with Client(mcp) as client_a:
            await client_a.call_tool(
                "update_set_draft",
                {"track_ids": [101, 102, 103], "name": "Session A Draft"},
            )
            draft_a = _read_draft_resource(await client_a.read_resource("session://set-draft"))
            assert draft_a["track_ids"] == [101, 102, 103]

        # Reset lifespan so Session B gets a fresh connection
        mcp._lifespan_result = None
        mcp._lifespan_result_set = False

        # Session B: must NOT see Session A's draft
        async with Client(mcp) as client_b:
            draft_b = _read_draft_resource(await client_b.read_resource("session://set-draft"))
            assert draft_b == {}, f"Session B should see empty draft but got: {draft_b}"
    finally:
        mcp._lifespan_result = None
        mcp._lifespan_result_set = False
        mcp._lifespan = original_lifespan


@pytest.mark.asyncio
async def test_preview_draft_100_tracks_performance(async_engine, patch_tiered_noop) -> None:
    """preview_draft with 100 tracks must complete without error."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)

    track_ids: list[int] = []
    async with factory() as session:
        for i in range(100):
            t = Track(title=f"Bulk Track {i}", status=0, duration_ms=180000)
            session.add(t)
            await session.flush()
            track_ids.append(t.id)
            session.add(
                TrackAudioFeaturesComputed(
                    track_id=t.id,
                    bpm=128.0 + (i % 10),
                    key_code=i % 24,  # 0..23
                    integrated_lufs=-10.0 - (i % 5),
                    energy_mean=0.5 + (i % 5) * 0.05,
                    spectral_centroid_hz=2000.0 + i * 10,
                    onset_rate=3.5 + (i % 4) * 0.3,
                    kick_prominence=0.5 + (i % 3) * 0.1,
                )
            )
        await session.commit()

    original_lifespan = mcp._lifespan
    mcp._lifespan = _build_lifespan(async_engine, factory)
    mcp._lifespan_result = None
    mcp._lifespan_result_set = False
    try:
        async with Client(mcp) as c:
            await c.call_tool(
                "update_set_draft",
                {"track_ids": track_ids, "name": "100 Track Set"},
            )
            data = parse_tool_result(await c.call_tool("preview_draft", {"narrative": False}))
            assert data["track_count"] == 100
            assert "score" in data
            assert isinstance(data["bpm_arc"], list)
            assert len(data["bpm_arc"]) == 100
    finally:
        mcp._lifespan_result = None
        mcp._lifespan_result_set = False
        mcp._lifespan = original_lifespan
