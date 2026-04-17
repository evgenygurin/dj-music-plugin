"""Acceptance test fixtures and helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastmcp import Client
from fastmcp.server.lifespan import lifespan
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.clients.ym.models import YMPlaylist, YMTrack
from app.core.constants import Provider
from app.core.utils.cache import TransitionCache
from app.providers.models import ProviderArtist, ProviderTrack
from app.server import mcp


@dataclass
class AcceptanceHarness:
    client: Client
    ym: AsyncMock
    session_factory: async_sessionmaker


def parse_tool_result(result):  # type: ignore[no-untyped-def]
    """Extract JSON data from a FastMCP CallToolResult."""
    if hasattr(result, "data") and isinstance(result.data, dict):
        return result.data
    content = getattr(result, "content", result)
    if isinstance(content, list) and len(content) > 0:
        block = content[0]
        text = getattr(block, "text", None) or str(block)
        return json.loads(text)
    if isinstance(result, dict):
        return result
    raise ValueError(f"Unexpected result type: {type(result)}")


def make_ym_track(
    track_id: str,
    title: str,
    *,
    artist: str = "Acceptance Artist",
    album_id: str = "9001",
    album_title: str = "Acceptance Album",
    duration_ms: int = 180000,
) -> YMTrack:
    """Create a deterministic YM track fixture (legacy dict-style)."""
    return YMTrack(
        id=track_id,
        title=title,
        duration_ms=duration_ms,
        artists=[{"name": artist}],
        albums=[{"id": album_id, "title": album_title, "genre": "techno", "year": 2024}],
    )


def make_provider_track(
    track_id: str,
    title: str,
    *,
    artist: str = "Acceptance Artist",
    album_id: str = "9001",
    album_title: str = "Acceptance Album",
    album_genre: str = "techno",
    duration_ms: int = 180000,
) -> ProviderTrack:
    """Create a deterministic ProviderTrack fixture for MusicProvider mocks."""
    return ProviderTrack(
        id=track_id,
        title=title,
        duration_ms=duration_ms,
        artists=[ProviderArtist(id="1", name=artist, provider=Provider.YANDEX_MUSIC)],
        album_id=album_id,
        album_title=album_title,
        album_genre=album_genre,
        provider=Provider.YANDEX_MUSIC,
    )


@pytest.fixture
def patch_audio_pipeline(monkeypatch: pytest.MonkeyPatch):
    """Patch audio analysis to deterministic lightweight results."""

    async def _fake_analyze(self, path: str, analyzers=None, return_context=False):  # type: ignore[no-untyped-def]
        del self, path, analyzers, return_context
        return SimpleNamespace(
            features={
                "bpm": 129.5,
                "bpm_confidence": 0.92,
                "energy_mean": 0.74,
                "integrated_lufs": -8.2,
                "spectral_centroid_hz": 2400.0,
                "onset_rate": 4.6,
                "kick_prominence": 0.71,
                "key_code": 8,
                "sections": [
                    {
                        "section_type": 1,
                        "start_ms": 0,
                        "end_ms": 60000,
                        "energy": 0.62,
                    }
                ],
            },
            analyzers_run=["energy", "tempo"],
            errors=[],
            context=None,
        )

    def _fake_classify(self, feat_dict):  # type: ignore[no-untyped-def]
        del self, feat_dict
        return SimpleNamespace(
            mood=SimpleNamespace(value="driving"),
            confidence=0.91,
            reasoning="deterministic",
        )

    monkeypatch.setattr("app.audio.pipeline.AnalysisPipeline.analyze", _fake_analyze)
    monkeypatch.setattr(
        "app.audio.classification.classifier.MoodClassifier.classify", _fake_classify
    )


@pytest.fixture
def patch_tiered_noop(monkeypatch: pytest.MonkeyPatch):
    """Patch tiered analysis to a deterministic no-op."""

    async def _fake_ensure_level(
        self, track_ids, target_level, *, force=False, progress_callback=None
    ):  # type: ignore[no-untyped-def]
        del self, target_level, force, progress_callback
        return {"analyzed": 0, "skipped": len(track_ids), "failed": 0}

    monkeypatch.setattr(
        "app.services.tiered_pipeline.TieredPipeline.ensure_level", _fake_ensure_level
    )


@pytest.fixture
async def acceptance_harness(async_engine, analyzer_registry) -> AcceptanceHarness:  # type: ignore[no-untyped-def]
    """FastMCP client harness with an in-memory DB and configurable YM mock."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    original_lifespan = mcp._lifespan

    registry = analyzer_registry
    cache = TransitionCache(max_size=100, ttl=60)

    ym_mock = AsyncMock()
    ym_mock.__aenter__.return_value = ym_mock
    ym_mock.__aexit__.return_value = None
    ym_mock.search = AsyncMock(
        return_value=SimpleNamespace(tracks=[], albums=[], artists=[], playlists=[])
    )
    ym_mock.get_liked_ids = AsyncMock(return_value=[])
    ym_mock.get_disliked_ids = AsyncMock(return_value=set())
    ym_mock.get_tracks = AsyncMock(return_value=[])
    ym_mock.get_playlist = AsyncMock(
        return_value=YMPlaylist(kind=42, title="Acceptance", revision=1)
    )
    ym_mock.get_playlist_tracks = AsyncMock(return_value=[])
    ym_mock.add_tracks_to_playlist = AsyncMock(return_value={"revision": 2})
    ym_mock.resolve_track_ids_with_albums = AsyncMock(side_effect=lambda ids: ids)
    ym_mock.close = AsyncMock()

    async def _download_track(
        track_id: str, dest_path: str | Path, *args: object, **kwargs: object
    ) -> int:
        del track_id, args, kwargs
        path = Path(dest_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = b"0" * 4096
        path.write_bytes(payload)
        return len(payload)

    ym_mock.download_track = AsyncMock(side_effect=_download_track)

    # Build a mock ProviderRegistry that wraps the ym_mock
    from app.providers.registry import ProviderRegistry

    provider_registry = ProviderRegistry()
    # ym_mock acts as both raw client and provider for tests
    ym_mock.provider = Provider.YANDEX_MUSIC
    ym_mock.get_stream_url = AsyncMock(return_value="https://fake.cdn/track.mp3")
    provider_registry._providers = {"yandex_music": ym_mock}  # type: ignore[dict-item]
    provider_registry._default = "yandex_music"  # type: ignore[assignment]

    @lifespan
    async def _test_lifespan(server):  # type: ignore[no-untyped-def]
        yield {
            "db_engine": async_engine,
            "db_session_factory": factory,
            "ym_client": ym_mock,
            "provider_registry": provider_registry,
            "analyzer_registry": registry,
            "transition_cache": cache,
        }

    mcp._lifespan = _test_lifespan
    mcp._lifespan_result = None
    mcp._lifespan_result_set = False

    try:
        async with Client(mcp) as client:
            # Unlock all hidden tool categories so acceptance tests can call any tool.
            # This triggers tools/list_changed → client re-fetches tool list.
            await client.call_tool("unlock_tools", {"action": "unlock", "category": "all"})
            yield AcceptanceHarness(client=client, ym=ym_mock, session_factory=factory)
    finally:
        mcp._lifespan_result = None
        mcp._lifespan_result_set = False
        mcp._lifespan = original_lifespan
