"""Targeted tests for the three live-fix areas from session df42c45.

1. search_library tokenized fallback ("Dok Martin" → "Dok & Martin")
2. preview_set_arc with set_id convenience param (no track_ids needed)
3. manage_set + manage_playlist tool descriptions — contain per-action examples

Run:
    uv run pytest tests/acceptance/test_live_fixes.py -v
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastmcp import Client
from fastmcp.server.lifespan import lifespan
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.clients.ym.models import YMPlaylist, YMTrack
from app.core.utils.cache import TransitionCache
from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.platform import YandexMetadata
from app.db.models.set import DjSet, SetItem, SetVersion
from app.db.models.track import Track, TrackExternalId
from app.providers.registry import ProviderRegistry
from app.server import mcp

# ── local fixtures (mirrors smoke test) ──────────────────────────────


@pytest.fixture
def patch_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deterministic audio analysis stub."""

    async def _fake_analyze(self, path, analyzers=None, return_context=False):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            features={
                "bpm": 133.0,
                "bpm_confidence": 0.95,
                "energy_mean": 0.75,
                "integrated_lufs": -9.0,
                "spectral_centroid_hz": 2500.0,
                "onset_rate": 4.8,
                "kick_prominence": 0.72,
                "key_code": 8,
                "sections": [{"section_type": 1, "start_ms": 0, "end_ms": 60000, "energy": 0.7}],
            },
            analyzers_run=["energy", "tempo"],
            errors=[],
            context=None,
        )

    def _fake_classify(self, feat_dict):  # type: ignore[no-untyped-def]
        from app.core.constants import TechnoSubgenre

        scores = {sg: 0.0 for sg in TechnoSubgenre}
        scores[TechnoSubgenre.DRIVING] = 0.92
        return SimpleNamespace(
            mood=SimpleNamespace(value="driving"),
            confidence=0.92,
            reasoning="deterministic",
            scores=scores,
        )

    monkeypatch.setattr("app.audio.pipeline.AnalysisPipeline.analyze", _fake_analyze)
    monkeypatch.setattr(
        "app.audio.classification.classifier.MoodClassifier.classify", _fake_classify
    )


@pytest.fixture
def patch_tiered(monkeypatch: pytest.MonkeyPatch) -> None:
    """No-op tiered pipeline."""

    async def _fake_ensure_level(
        self, track_ids, target_level, *, force=False, progress_callback=None
    ):  # type: ignore[no-untyped-def]
        return {"analyzed": 0, "skipped": len(track_ids or []), "failed": 0}

    monkeypatch.setattr(
        "app.services.tiered_pipeline.TieredPipeline.ensure_level", _fake_ensure_level
    )


# ── helpers ──────────────────────────────────────────────────────────


def _parse(result: Any) -> Any:
    if hasattr(result, "data") and isinstance(result.data, dict | list):
        return result.data
    if hasattr(result, "data") and hasattr(result.data, "model_dump"):
        return result.data.model_dump()
    content = getattr(result, "content", result)
    if isinstance(content, list) and content:
        text = getattr(content[0], "text", None) or str(content[0])
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return text
    if isinstance(result, dict):
        return result
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return result


async def _tool(client: Any, name: str, args: dict | None = None) -> Any:
    r = await client.call_tool(name, args or {})
    return _parse(r)


def _make_ym_track(tid: str = "100") -> YMTrack:
    return YMTrack(
        id=tid,
        title="Test Track",
        duration_ms=360000,
        artists=[{"name": "Test Artist"}],
        albums=[{"id": "9", "title": "Test Album", "genre": "techno", "year": 2024}],
    )


def _search_tracks(r: Any) -> list[dict]:
    """Extract tracks list from search_library response.

    search_library returns ``{"query": ..., "total": ..., "results": {"tracks": [...], ...}}``.
    """
    if isinstance(r, list):
        return r
    results = r.get("results", r)
    if isinstance(results, dict):
        return results.get("tracks", [])
    return []


# ── fixture ──────────────────────────────────────────────────────────


@pytest.fixture
async def fx(async_engine, patch_audio, patch_tiered, analyzer_registry):  # type: ignore[no-untyped-def]
    """Minimal smoke harness seeded with tracks whose names test tokenized search."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    original_lifespan = mcp._lifespan

    registry = analyzer_registry
    cache = TransitionCache(max_size=100, ttl=60)

    ym = AsyncMock()
    ym.__aenter__.return_value = ym
    ym.__aexit__.return_value = None
    ym.search = AsyncMock(
        return_value=SimpleNamespace(tracks=[], albums=[], artists=[], playlists=[])
    )
    ym.get_liked_ids = AsyncMock(return_value=[])
    ym.get_disliked_ids = AsyncMock(return_value=set())
    ym.get_tracks = AsyncMock(return_value=[_make_ym_track()])
    ym.get_playlist = AsyncMock(
        return_value=YMPlaylist(kind=42, title="Test Playlist", revision=1)
    )
    ym.get_playlist_tracks = AsyncMock(return_value=[])
    ym.close = AsyncMock()

    provider_registry = ProviderRegistry()
    provider_registry._providers = {"yandex_music": ym}  # type: ignore[dict-item]
    provider_registry._default = "yandex_music"  # type: ignore[assignment]

    track_id: int
    track_id2: int
    track_id3: int
    set_id: int

    async with factory() as session:
        # Three tracks with special chars or multi-token titles to test search
        t1 = Track(title="Dok & Martin - Deep Dive", status=0, duration_ms=360000)
        t2 = Track(title="Acid Test (Remix)", status=0, duration_ms=300000)
        t3 = Track(title="Dark Techno Warrior", status=0, duration_ms=420000)
        session.add_all([t1, t2, t3])
        await session.flush()
        track_id, track_id2, track_id3 = t1.id, t2.id, t3.id

        for tid, bpm in ((t1.id, 133.0), (t2.id, 136.0), (t3.id, 140.0)):
            session.add(
                TrackAudioFeaturesComputed(
                    track_id=tid,
                    bpm=bpm,
                    key_code=8,
                    integrated_lufs=-9.0,
                    energy_mean=0.75,
                    spectral_centroid_hz=2500.0,
                    analysis_level=3,
                )
            )

        dj_set = DjSet(name="Live Fix Set", template_name="roller_90")
        session.add(dj_set)
        await session.flush()
        set_id = dj_set.id

        sv = SetVersion(set_id=dj_set.id, label="v1")
        session.add(sv)
        await session.flush()

        session.add_all(
            [
                SetItem(version_id=sv.id, track_id=t1.id, sort_index=0),
                SetItem(version_id=sv.id, track_id=t2.id, sort_index=1),
            ]
        )

        session.add(YandexMetadata(track_id=t1.id, yandex_track_id="100", album_id="9"))
        session.add(TrackExternalId(track_id=t1.id, platform="yandex_music", external_id="100"))
        session.add(YandexMetadata(track_id=t2.id, yandex_track_id="101", album_id="9"))
        session.add(TrackExternalId(track_id=t2.id, platform="yandex_music", external_id="101"))

        await session.commit()

    @lifespan
    async def _ls(server):  # type: ignore[no-untyped-def]
        yield {
            "db_engine": async_engine,
            "db_session_factory": factory,
            "ym_client": ym,
            "provider_registry": provider_registry,
            "analyzer_registry": registry,
            "transition_cache": cache,
        }

    mcp._lifespan = _ls
    mcp._lifespan_result = None
    mcp._lifespan_result_set = False

    try:
        async with Client(mcp) as client:
            await client.call_tool("unlock_tools", {"action": "unlock", "category": "all"})
            yield {
                "client": client,
                "track_id": track_id,
                "track_id2": track_id2,
                "track_id3": track_id3,
                "set_id": set_id,
            }
    finally:
        mcp._lifespan_result = None
        mcp._lifespan_result_set = False
        mcp._lifespan = original_lifespan


# ── 1. search tokenized fallback ─────────────────────────────────────


@pytest.mark.asyncio
async def test_search_special_chars_ampersand(fx: dict) -> None:
    """'Dok Martin' (no &) must find 'Dok & Martin - Deep Dive' via token fallback."""
    r = await _tool(fx["client"], "search_library", {"query": "Dok Martin"})
    titles = [t.get("title", "") for t in _search_tracks(r)]
    assert any("Dok" in t and "Martin" in t for t in titles), (
        f"Expected 'Dok & Martin' in results, got titles={titles}, response={r}"
    )


@pytest.mark.asyncio
async def test_search_special_chars_acid_test(fx: dict) -> None:
    """'acid test' must find 'Acid Test (Remix)' via case-insensitive token match."""
    r = await _tool(fx["client"], "search_library", {"query": "acid test"})
    titles = [t.get("title", "") for t in _search_tracks(r)]
    assert any("Acid Test" in t for t in titles), (
        f"Expected 'Acid Test' in results, got titles={titles}, response={r}"
    )


@pytest.mark.asyncio
async def test_search_multi_token(fx: dict) -> None:
    """'dark techno' must find 'Dark Techno Warrior' via two-token AND match."""
    r = await _tool(fx["client"], "search_library", {"query": "dark techno"})
    titles = [t.get("title", "") for t in _search_tracks(r)]
    assert any("Dark Techno" in t for t in titles), (
        f"Expected 'Dark Techno Warrior' in results, got titles={titles}, response={r}"
    )


# ── 2. preview_set_arc with set_id ───────────────────────────────────


@pytest.mark.asyncio
async def test_preview_set_arc_with_set_id(fx: dict) -> None:
    """preview_set_arc(set_id=N) must auto-load tracks without requiring track_ids."""
    r = await _tool(fx["client"], "preview_set_arc", {"set_id": fx["set_id"]})
    assert "score" in r, f"Expected 'score' in result, got: {r}"
    # Set has 2 tracks — bpm_arc should have 2 entries
    bpm_arc = r.get("bpm_arc", [])
    assert len(bpm_arc) >= 2, (
        f"Expected set_id to load 2 tracks (bpm_arc len >= 2), got: bpm_arc={bpm_arc}, r={r}"
    )


@pytest.mark.asyncio
async def test_preview_set_arc_track_ids_priority(fx: dict) -> None:
    """track_ids takes priority over set_id when both provided."""
    r = await _tool(
        fx["client"],
        "preview_set_arc",
        {"set_id": fx["set_id"], "track_ids": [fx["track_id"]]},
    )
    assert "score" in r, f"Expected 'score' in result, got: {r}"
    # Only 1 track_id given; set has 2. If track_ids wins, bpm_arc has 1 entry
    bpm_arc = r.get("bpm_arc", [])
    assert len(bpm_arc) == 1, (
        f"Expected track_ids to take priority (bpm_arc len=1), got: bpm_arc={bpm_arc}, r={r}"
    )


# ── 3. tool descriptions contain per-action examples ─────────────────


@pytest.mark.asyncio
async def test_manage_set_description_has_action_examples(fx: dict) -> None:
    """manage_set description must mention each action with payload examples."""
    tools = await fx["client"].list_tools()
    tool = next((t for t in tools if t.name == "manage_set"), None)
    assert tool is not None, "manage_set not found in tool list"
    desc = tool.description or ""
    for action in ("create", "update", "delete"):
        assert action in desc.lower(), (
            f"manage_set description missing action '{action}'. Description: {desc[:400]}"
        )


@pytest.mark.asyncio
async def test_manage_playlist_description_has_structure_hint(fx: dict) -> None:
    """manage_playlist description must clarify track_refs is top-level, not inside data."""
    tools = await fx["client"].list_tools()
    tool = next((t for t in tools if t.name == "manage_playlist"), None)
    assert tool is not None, "manage_playlist not found in tool list"

    desc = tool.description or ""
    param_descs = ""
    if hasattr(tool, "inputSchema") and tool.inputSchema:
        props = tool.inputSchema.get("properties", {})
        for prop in props.values():
            param_descs += prop.get("description", "")

    combined = (desc + param_descs).lower()
    assert "track_refs" in combined, (
        f"manage_playlist docs missing 'track_refs' mention. Combined: {combined[:400]}"
    )
