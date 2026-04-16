"""End-to-end smoke test for ALL MCP components.

Verifies that every tool, resource, and prompt can be invoked without
crashing. External dependencies (YM API, audio pipeline) are mocked.

Run:
    uv run pytest tests/acceptance/test_smoke_all_components.py -v
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import Client
from fastmcp.server.lifespan import lifespan
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.clients.ym.models import YMPlaylist, YMTrack
from app.core.constants import Provider
from app.core.utils.cache import TransitionCache
from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.platform import YandexMetadata
from app.db.models.playlist import Playlist, PlaylistItem
from app.db.models.set import DjSet, SetItem, SetVersion
from app.db.models.track import Track, TrackExternalId
from app.providers.models import ProviderPlaylist
from app.providers.registry import ProviderRegistry
from app.server import mcp

# ── Helpers ───────────────────────────────────────────────────────────


def _parse(result: Any) -> Any:
    """Extract data from a FastMCP CallToolResult (handles dict / Pydantic / JSON text)."""
    # FastMCP v3 structured return
    if hasattr(result, "data") and isinstance(result.data, dict):
        return result.data
    if hasattr(result, "data") and isinstance(result.data, list):
        return result.data
    # Pydantic model returned as data
    if hasattr(result, "data") and hasattr(result.data, "model_dump"):
        return result.data.model_dump()
    # Text content (JSON serialized)
    content = getattr(result, "content", result)
    if isinstance(content, list) and content:
        text = getattr(content[0], "text", None) or str(content[0])
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return text
    if isinstance(result, dict):
        return result
    # Last resort: try model_dump on result itself
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return result


def _text(result: Any) -> str:
    """Extract raw text from a resource read result."""
    if isinstance(result, list) and result:
        return getattr(result[0], "text", str(result[0]))
    return str(result)


def _make_ym_track(tid: str = "100") -> YMTrack:
    return YMTrack(
        id=tid,
        title="Smoke Track",
        duration_ms=360000,
        artists=[{"name": "Smoke Artist"}],
        albums=[{"id": "9", "title": "Smoke Album", "genre": "techno", "year": 2024}],
    )


# ── Fixtures ──────────────────────────────────────────────────────────


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


@pytest.fixture
async def smoke(async_engine, patch_audio, patch_tiered, analyzer_registry):  # type: ignore[no-untyped-def]
    """Full smoke harness: MCP client + in-memory DB with seed data."""
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    original_lifespan = mcp._lifespan

    registry = analyzer_registry
    cache = TransitionCache(max_size=100, ttl=60)

    # ── YM mock ──────────────────────────────────────────────────────
    ym = AsyncMock()
    ym.provider = Provider.YANDEX_MUSIC
    ym.__aenter__.return_value = ym
    ym.__aexit__.return_value = None
    ym.search = AsyncMock(
        return_value=SimpleNamespace(tracks=[], albums=[], artists=[], playlists=[])
    )
    ym.get_liked_ids = AsyncMock(return_value=["100"])
    ym.get_disliked_ids = AsyncMock(return_value=set())
    ym.get_tracks = AsyncMock(return_value=[_make_ym_track()])
    ym.get_playlist = AsyncMock(
        return_value=YMPlaylist(kind=42, title="Smoke Playlist", revision=1)
    )
    ym.get_playlist_tracks = AsyncMock(return_value=[_make_ym_track()])
    ym.add_tracks_to_playlist = AsyncMock(return_value={"revision": 2})
    ym.create_playlist = AsyncMock(
        return_value=ProviderPlaylist(
            id="42069:42", title="Smoke Playlist", provider=Provider.YANDEX_MUSIC
        )
    )
    ym.resolve_track_ids_with_albums = AsyncMock(side_effect=lambda ids: ids)
    ym.get_stream_url = AsyncMock(return_value="https://fake.cdn/track.mp3")
    ym.close = AsyncMock()

    async def _download(track_id, dest_path, *a, **kw):  # type: ignore[no-untyped-def]
        from pathlib import Path

        p = Path(dest_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"0" * 4096)
        return 4096

    ym.download_track = AsyncMock(side_effect=_download)

    # ── Provider registry mock ────────────────────────────────────────
    provider_mock = MagicMock()
    provider_mock.provider = Provider.YANDEX_MUSIC
    provider_registry = ProviderRegistry()
    provider_registry._providers = {"yandex_music": ym}  # type: ignore[dict-item]
    provider_registry._default = "yandex_music"  # type: ignore[assignment]

    # ── Seed DB with minimal data ─────────────────────────────────────
    track_id: int
    track_id2: int
    set_id: int
    playlist_id: int

    async with factory() as session:
        t1 = Track(title="Smoke Alpha", status=0, duration_ms=360000)
        t2 = Track(title="Smoke Beta", status=0, duration_ms=300000)
        session.add_all([t1, t2])
        await session.flush()
        track_id = t1.id
        track_id2 = t2.id

        # Audio features for both tracks
        for tid, bpm in ((t1.id, 133.0), (t2.id, 136.0)):
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

        # DJ set with two tracks
        dj_set = DjSet(name="Smoke Set", template_name="roller_90")
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

        # YM metadata for tracks (needed for push_set_to_platform)
        session.add(YandexMetadata(track_id=t1.id, yandex_track_id="100", album_id="9"))
        session.add(YandexMetadata(track_id=t2.id, yandex_track_id="101", album_id="9"))
        # TrackExternalId links used by sync_service._collect_ym_track_ids
        session.add(TrackExternalId(track_id=t1.id, platform="yandex_music", external_id="100"))
        session.add(TrackExternalId(track_id=t2.id, platform="yandex_music", external_id="101"))

        # Playlist with YM link (needed for sync_playlist)
        pl = Playlist(
            name="Smoke Playlist",
            source_of_truth="local",
            platform_ids='{"yandex_music": "42"}',
        )
        session.add(pl)
        await session.flush()
        playlist_id = pl.id

        session.add(PlaylistItem(playlist_id=pl.id, track_id=t1.id, sort_index=0))
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
            # Unlock all hidden categories
            await client.call_tool("unlock_tools", {"action": "unlock", "category": "all"})
            yield {
                "client": client,
                "ym": ym,
                "track_id": track_id,
                "track_id2": track_id2,
                "set_id": set_id,
                "playlist_id": playlist_id,
            }
    finally:
        mcp._lifespan_result = None
        mcp._lifespan_result_set = False
        mcp._lifespan = original_lifespan


# ── Helper: call tool and assert no crash ─────────────────────────────


async def _tool(client: Client, name: str, args: dict[str, Any] | None = None) -> Any:
    result = await client.call_tool(name, args or {})
    data = _parse(result)
    assert data is not None, f"{name}: returned None"
    return data


# ═══════════════════════════════════════════════════════════════════════
# TOOLS
# ═══════════════════════════════════════════════════════════════════════


# ── admin.py ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_unlock_tools_status(smoke: dict) -> None:
    """unlock_tools(status) — admin tool already called in fixture."""
    r = await _tool(smoke["client"], "unlock_tools", {"action": "status"})
    assert "effective" in r or "action" in r


@pytest.mark.asyncio
async def test_admin_list_platforms(smoke: dict) -> None:
    r = await _tool(smoke["client"], "list_platforms")
    assert isinstance(r, list)


# ── tracks.py ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tracks_list_tracks(smoke: dict) -> None:
    r = await _tool(smoke["client"], "list_tracks")
    assert "items" in r


@pytest.mark.asyncio
async def test_tracks_list_tracks_bpm_filter(smoke: dict) -> None:
    r = await _tool(smoke["client"], "list_tracks", {"bpm_min": 120.0, "bpm_max": 140.0})
    assert "items" in r


@pytest.mark.asyncio
async def test_tracks_get_track(smoke: dict) -> None:
    r = await _tool(smoke["client"], "get_track", {"id": smoke["track_id"]})
    assert r["id"] == smoke["track_id"]


@pytest.mark.asyncio
async def test_tracks_manage_create(smoke: dict) -> None:
    r = await _tool(
        smoke["client"], "manage_tracks", {"action": "create", "data": {"title": "New Track"}}
    )
    assert "id" in r


@pytest.mark.asyncio
async def test_tracks_manage_archive(smoke: dict) -> None:
    # Create then archive
    created = _parse(
        await smoke["client"].call_tool(
            "manage_tracks", {"action": "create", "data": {"title": "Temp Track"}}
        )
    )
    r = await _tool(
        smoke["client"], "manage_tracks", {"action": "archive", "data": {"id": created["id"]}}
    )
    assert r["id"] == created["id"]


@pytest.mark.asyncio
async def test_tracks_get_track_features(smoke: dict) -> None:
    r = await _tool(smoke["client"], "get_track_features", {"id": smoke["track_id"]})
    assert r["track_id"] == smoke["track_id"]


# ── sets.py ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sets_list_sets(smoke: dict) -> None:
    r = await _tool(smoke["client"], "list_sets")
    assert "items" in r


@pytest.mark.asyncio
async def test_sets_get_set(smoke: dict) -> None:
    r = await _tool(smoke["client"], "get_set", {"id": smoke["set_id"]})
    assert "id" in r or "name" in r


@pytest.mark.asyncio
async def test_sets_manage_create(smoke: dict) -> None:
    r = await _tool(
        smoke["client"], "manage_set", {"action": "create", "data": {"name": "Smoke Set 2"}}
    )
    assert "id" in r


@pytest.mark.asyncio
async def test_sets_commit_set_version(smoke: dict) -> None:
    r = await _tool(
        smoke["client"],
        "commit_set_version",
        {
            "name": "Smoke Committed",
            "track_ids": [smoke["track_id"], smoke["track_id2"]],
        },
    )
    assert "set_id" in r
    assert "version_id" in r


@pytest.mark.asyncio
async def test_sets_get_set_templates(smoke: dict) -> None:
    r = await _tool(smoke["client"], "get_set_templates")
    assert "templates" in r
    assert len(r["templates"]) > 0


@pytest.mark.asyncio
async def test_sets_preview_set_arc(smoke: dict) -> None:
    r = await _tool(
        smoke["client"],
        "preview_set_arc",
        {"track_ids": [smoke["track_id"], smoke["track_id2"]]},
    )
    assert "score" in r


@pytest.mark.asyncio
async def test_sets_preview_set_arc_empty(smoke: dict) -> None:
    r = await _tool(smoke["client"], "preview_set_arc", {"track_ids": []})
    assert "score" in r


@pytest.mark.asyncio
async def test_sets_score_transitions(smoke: dict) -> None:
    r = await _tool(
        smoke["client"],
        "score_transitions",
        {"mode": "pair", "from_track_id": smoke["track_id"], "to_track_id": smoke["track_id2"]},
    )
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_sets_search_transitions(smoke: dict) -> None:
    # Ensure at least one scored row exists, then search with filters/projection/sort.
    await _tool(
        smoke["client"],
        "score_transitions",
        {"mode": "pair", "from_track_id": smoke["track_id"], "to_track_id": smoke["track_id2"]},
    )
    r = await _tool(
        smoke["client"],
        "search_transitions",
        {
            "limit": 10,
            "offset": 0,
            "sort_by": "-overall_quality",
            "filters": {"hard_reject": False},
            "include_fields": ["from_track_id", "to_track_id", "overall_quality", "hard_reject"],
            "include_stats": True,
        },
    )
    assert "rows" in r
    assert "fields" in r
    assert "stats" in r
    assert set(r["fields"]) == {"selected", "excluded"}
    assert r.get("filter_operators") is None


@pytest.mark.asyncio
async def test_sets_search_transitions_default_projection_id_only(smoke: dict) -> None:
    """Omit include_fields → each row must expose only ``id`` (slim MCP default)."""
    await _tool(
        smoke["client"],
        "score_transitions",
        {"mode": "pair", "from_track_id": smoke["track_id"], "to_track_id": smoke["track_id2"]},
    )
    r = await _tool(
        smoke["client"],
        "search_transitions",
        {"limit": 5, "offset": 0, "include_stats": False},
    )
    assert r.get("rows"), "expected at least one transition row"
    for row in r["rows"]:
        assert set(row.keys()) == {"id"}, row
    assert r.get("stats") is None
    assert set(r["fields"]) == {"selected", "excluded"}


@pytest.mark.asyncio
async def test_sets_get_set_cheat_sheet(smoke: dict) -> None:
    r = await smoke["client"].call_tool("get_set_cheat_sheet", {"set_id": smoke["set_id"]})
    data = _parse(r)
    assert isinstance(data, dict)
    assert "cheat_sheet" in data and isinstance(data["cheat_sheet"], str)
    assert "cheat_sheet_lines" in data and isinstance(data["cheat_sheet_lines"], list)
    assert data["cheat_sheet"] == "\n".join(data["cheat_sheet_lines"])
    assert data.get("set_id") == smoke["set_id"]


# ── search.py ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_library(smoke: dict) -> None:
    r = await _tool(smoke["client"], "search_library", {"query": "Smoke"})
    assert "tracks" in r or "results" in r or isinstance(r, dict)


# ── playlists.py ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_playlists_list(smoke: dict) -> None:
    r = await _tool(smoke["client"], "list_playlists")
    assert "items" in r


@pytest.mark.asyncio
async def test_playlists_get(smoke: dict) -> None:
    r = await _tool(smoke["client"], "get_playlist", {"id": smoke["playlist_id"]})
    assert "id" in r or "title" in r


@pytest.mark.asyncio
async def test_playlists_manage_create(smoke: dict) -> None:
    r = await _tool(
        smoke["client"],
        "manage_playlist",
        {"action": "create", "data": {"name": "Smoke Pl 2"}},
    )
    assert "id" in r or isinstance(r, dict)


# ── draft.py ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_draft_update(smoke: dict) -> None:
    r = await _tool(
        smoke["client"],
        "update_set_draft",
        {"track_ids": [smoke["track_id"], smoke["track_id2"]]},
    )
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_draft_preview(smoke: dict) -> None:
    await smoke["client"].call_tool(
        "update_set_draft", {"track_ids": [smoke["track_id"], smoke["track_id2"]]}
    )
    r = await _tool(smoke["client"], "preview_draft")
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_draft_clear(smoke: dict) -> None:
    r = await _tool(smoke["client"], "clear_draft")
    assert isinstance(r, dict)


# ── curation.py ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_curation_get_library_stats(smoke: dict) -> None:
    r = await _tool(smoke["client"], "get_library_stats")
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_curation_classify_mood_with_tracks(smoke: dict) -> None:
    r = await _tool(smoke["client"], "classify_mood", {"track_ids": [smoke["track_id"]]})
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_curation_audit_playlist(smoke: dict) -> None:
    r = await _tool(smoke["client"], "audit_playlist", {"playlist_id": smoke["playlist_id"]})
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_curation_distribute_to_subgenres_dry_run(smoke: dict) -> None:
    r = await _tool(
        smoke["client"],
        "distribute_to_subgenres",
        {"source_playlist_id": smoke["playlist_id"], "dry_run": True},
    )
    assert isinstance(r, dict)


# ── candidate_pool.py ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_candidate_pool(smoke: dict) -> None:
    r = await _tool(smoke["client"], "get_candidate_pool", {"bpm_min": 128.0, "bpm_max": 140.0})
    assert "candidates" in r or isinstance(r, dict)


# ── audio.py ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audio_classify_track(smoke: dict) -> None:
    r = await _tool(smoke["client"], "classify_track", {"track_id": smoke["track_id"]})
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_audio_gate_track(smoke: dict) -> None:
    r = await _tool(smoke["client"], "gate_track", {"track_id": smoke["track_id"]})
    assert "pass" in r or "passed" in r or isinstance(r, dict)


@pytest.mark.asyncio
async def test_audio_get_similar_tracks(smoke: dict) -> None:
    r = await _tool(smoke["client"], "get_similar_tracks", {"ym_track_id": "100", "limit": 5})
    assert isinstance(r, dict | list)


@pytest.mark.asyncio
async def test_audio_analyze_track(smoke: dict) -> None:
    r = await _tool(smoke["client"], "analyze_track", {"track_id": smoke["track_id"]})
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_audio_analyze_batch_with_tracks(smoke: dict) -> None:
    r = await _tool(smoke["client"], "analyze_batch", {"track_ids": [smoke["track_id"]]})
    assert isinstance(r, dict)


# ── memory.py ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_track_feedback_list_liked(smoke: dict) -> None:
    r = await _tool(smoke["client"], "track_feedback", {"action": "list_liked"})
    assert isinstance(r, dict | list)


@pytest.mark.asyncio
async def test_memory_track_feedback_like(smoke: dict) -> None:
    r = await _tool(
        smoke["client"], "track_feedback", {"action": "like", "track_id": smoke["track_id"]}
    )
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_memory_transition_history_list(smoke: dict) -> None:
    r = await _tool(smoke["client"], "transition_history", {"action": "list"})
    assert isinstance(r, dict | list)


@pytest.mark.asyncio
async def test_memory_track_affinity_refresh(smoke: dict) -> None:
    r = await _tool(smoke["client"], "track_affinity", {"action": "refresh"})
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_memory_scoring_profile_list(smoke: dict) -> None:
    r = await _tool(smoke["client"], "scoring_profile", {"action": "list"})
    assert isinstance(r, dict | list)


@pytest.mark.asyncio
async def test_memory_session_arc_trend(smoke: dict) -> None:
    r = await _tool(smoke["client"], "session_arc", {"action": "trend"})
    assert isinstance(r, dict)


# ── reasoning.py ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reasoning_explain_transition(smoke: dict) -> None:
    r = await _tool(
        smoke["client"],
        "explain_transition",
        {"from_track_id": smoke["track_id"], "to_track_id": smoke["track_id2"]},
    )
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_reasoning_suggest_next_track(smoke: dict) -> None:
    r = await _tool(
        smoke["client"],
        "suggest_next_track",
        {"set_id": smoke["set_id"], "after_position": 0},
    )
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_reasoning_find_replacement(smoke: dict) -> None:
    r = await _tool(
        smoke["client"],
        "find_replacement",
        {"set_id": smoke["set_id"], "position": 0},
    )
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_reasoning_compare_set_versions(smoke: dict) -> None:
    # Only one version exists — tool should handle it gracefully
    r = await _tool(
        smoke["client"],
        "compare_set_versions",
        {"set_id": smoke["set_id"], "version_a": 1, "version_b": 1},
    )
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_reasoning_quick_set_review(smoke: dict) -> None:
    r = await _tool(smoke["client"], "quick_set_review", {"set_id": smoke["set_id"]})
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_reasoning_analyze_set_narrative(smoke: dict) -> None:
    r = await _tool(smoke["client"], "analyze_set_narrative", {"set_id": smoke["set_id"]})
    assert isinstance(r, dict)


# ── discovery.py ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discovery_filter_by_feedback(smoke: dict) -> None:
    r = await _tool(smoke["client"], "filter_by_feedback", {"ym_track_ids": ["100", "200"]})
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_discovery_expand_platform_playlist(smoke: dict) -> None:
    r = await _tool(
        smoke["client"],
        "expand_platform_playlist",
        {"playlist_id": "42", "target_count": 5},
    )
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_discovery_find_similar_tracks_ym(smoke: dict) -> None:
    r = await _tool(
        smoke["client"],
        "find_similar_tracks",
        {"track_id": smoke["track_id"], "strategy": "ym", "limit": 3},
    )
    assert isinstance(r, dict)


# ── importing.py ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_importing_import_tracks(smoke: dict) -> None:
    r = await _tool(smoke["client"], "import_tracks", {"track_refs": ["100"]})
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_importing_download_tracks(smoke: dict) -> None:
    r = await _tool(smoke["client"], "download_tracks", {"track_refs": ["100"]})
    assert isinstance(r, dict)


# ── sync.py ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_playlist_diff(smoke: dict) -> None:
    r = await _tool(
        smoke["client"],
        "sync_playlist",
        {"playlist_id": smoke["playlist_id"], "direction": "diff", "dry_run": True},
    )
    assert isinstance(r, dict)


@pytest.mark.asyncio
async def test_sync_push_set_to_platform(smoke: dict) -> None:
    r = await _tool(
        smoke["client"],
        "push_set_to_platform",
        {"set_id": smoke["set_id"]},
    )
    assert isinstance(r, dict)


# ── delivery.py ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delivery_deliver_set_dry_run(smoke: dict) -> None:
    r = await _tool(
        smoke["client"],
        "deliver_set",
        {"set_id": smoke["set_id"], "dry_run": True, "copy_files": False},
    )
    assert isinstance(r, dict)


# ═══════════════════════════════════════════════════════════════════════
# RESOURCES
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_resource_session_draft(smoke: dict) -> None:
    result = await smoke["client"].read_resource("session://set-draft")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_track_features(smoke: dict) -> None:
    result = await smoke["client"].read_resource(f"track://{smoke['track_id']}/features")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_track_identity(smoke: dict) -> None:
    result = await smoke["client"].read_resource(f"track://{smoke['track_id']}/identity")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_track_sections(smoke: dict) -> None:
    result = await smoke["client"].read_resource(f"track://{smoke['track_id']}/sections")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_set_summary(smoke: dict) -> None:
    result = await smoke["client"].read_resource(f"set://{smoke['set_id']}/summary")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_set_diagnostics(smoke: dict) -> None:
    result = await smoke["client"].read_resource(f"set://{smoke['set_id']}/diagnostics")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_playlist_status(smoke: dict) -> None:
    result = await smoke["client"].read_resource(f"playlist://{smoke['playlist_id']}/status")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_playlist_profile(smoke: dict) -> None:
    result = await smoke["client"].read_resource(f"playlist://{smoke['playlist_id']}/profile")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_catalog_stats(smoke: dict) -> None:
    result = await smoke["client"].read_resource("catalog://stats")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_knowledge_vocabulary(smoke: dict) -> None:
    result = await smoke["client"].read_resource("knowledge://vocabulary")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_knowledge_subgenre_culture(smoke: dict) -> None:
    result = await smoke["client"].read_resource("knowledge://subgenre-culture")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_knowledge_set_dynamics(smoke: dict) -> None:
    result = await smoke["client"].read_resource("knowledge://set-dynamics")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_knowledge_dancefloor_psychology(smoke: dict) -> None:
    result = await smoke["client"].read_resource("knowledge://dancefloor-psychology")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_knowledge_audio_features_field_guide(smoke: dict) -> None:
    result = await smoke["client"].read_resource("knowledge://audio-features-field-guide")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_reference_templates(smoke: dict) -> None:
    result = await smoke["client"].read_resource("reference://templates")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_reference_subgenres(smoke: dict) -> None:
    result = await smoke["client"].read_resource("reference://subgenres")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_reference_camelot(smoke: dict) -> None:
    result = await smoke["client"].read_resource("reference://camelot")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_reference_key_graph(smoke: dict) -> None:
    result = await smoke["client"].read_resource("reference://key-graph")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_library_snapshot(smoke: dict) -> None:
    result = await smoke["client"].read_resource("library://snapshot")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_library_prep_state(smoke: dict) -> None:
    result = await smoke["client"].read_resource("library://prep-state")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_status_library(smoke: dict) -> None:
    result = await smoke["client"].read_resource("status://library")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_status_platforms(smoke: dict) -> None:
    result = await smoke["client"].read_resource("status://platforms")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_status_analysis_quality(smoke: dict) -> None:
    result = await smoke["client"].read_resource("status://analysis-quality")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_status_set_integrity(smoke: dict) -> None:
    result = await smoke["client"].read_resource("status://set-integrity")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_status_provider_coverage(smoke: dict) -> None:
    result = await smoke["client"].read_resource("status://provider-coverage")
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_transition_recipe(smoke: dict) -> None:
    result = await smoke["client"].read_resource(
        f"transition://{smoke['track_id']}/{smoke['track_id2']}/recipe"
    )
    assert _text(result) is not None


@pytest.mark.asyncio
async def test_resource_exports_recent(smoke: dict) -> None:
    result = await smoke["client"].read_resource("exports://recent")
    assert _text(result) is not None


# ═══════════════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════════════


async def _prompt(client: Client, name: str, args: dict[str, Any] | None = None) -> list:
    result = await client.get_prompt(name, args or {})
    msgs = getattr(result, "messages", result)
    assert isinstance(msgs, list) and len(msgs) > 0, f"Prompt {name}: empty messages"
    return msgs


@pytest.mark.asyncio
async def test_prompt_build_set_workflow(smoke: dict) -> None:
    msgs = await _prompt(
        smoke["client"],
        "build_set_workflow",
        {"playlist_name": "Smoke Playlist", "template": "classic_60", "duration_min": 60},
    )
    assert msgs


@pytest.mark.asyncio
async def test_prompt_full_expansion_pipeline(smoke: dict) -> None:
    msgs = await _prompt(
        smoke["client"],
        "full_expansion_pipeline",
        {"source_playlist": "TECHNO FOR DJ SETS", "target_per_subgenre": 10},
    )
    assert msgs


@pytest.mark.asyncio
async def test_prompt_expand_playlist_workflow(smoke: dict) -> None:
    msgs = await _prompt(
        smoke["client"],
        "expand_playlist_workflow",
        {"playlist_name": "Smoke Playlist", "target_count": 20},
    )
    assert msgs


@pytest.mark.asyncio
async def test_prompt_deliver_set_workflow(smoke: dict) -> None:
    msgs = await _prompt(
        smoke["client"],
        "deliver_set_workflow",
        {"set_name": "Smoke Set"},
    )
    assert msgs


@pytest.mark.asyncio
async def test_prompt_improve_set_workflow(smoke: dict) -> None:
    msgs = await _prompt(
        smoke["client"],
        "improve_set_workflow",
        {"set_name": "Smoke Set"},
    )
    assert msgs


@pytest.mark.asyncio
async def test_prompt_dj_expert_session(smoke: dict) -> None:
    msgs = await _prompt(smoke["client"], "dj_expert_session", {"goal": "dark hypnotic"})
    assert msgs
    user_text = ""
    for m in msgs:
        role = getattr(m, "role", None)
        if role == "user":
            content = getattr(m, "content", "")
            user_text = getattr(content, "text", content) if content is not None else ""
            if isinstance(user_text, str):
                break
    assert "track://{track_id}/features" in user_text
    assert "built-in function id" not in user_text


@pytest.mark.asyncio
async def test_prompt_llm_discovery_workflow(smoke: dict) -> None:
    msgs = await _prompt(
        smoke["client"],
        "llm_discovery_workflow",
        {"track_name": "Smoke Alpha", "limit": 5},
    )
    assert msgs
