"""Acceptance test for the declarative draft set flow."""

from __future__ import annotations

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
