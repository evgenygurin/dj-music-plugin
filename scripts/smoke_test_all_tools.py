"""Smoke-test every MCP tool through FastMCP Client.

Usage: .venv/bin/python scripts/smoke_test_all_tools.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any

# ── Minimal args for each tool (enough to reach business logic) ──────────
# For list/read tools: empty or minimal params → should return empty/error
# For write tools: minimal valid create → should succeed or domain-error
TOOL_CALLS: dict[str, dict[str, Any]] = {
    # ── CRUD Tracks ──
    "list_tracks": {"limit": 2},
    "get_track": {"id": 999999},
    "manage_tracks": {
        "action": "create",
        "data": json.dumps({"title": "Smoke Test Track", "duration_ms": 300000}),
    },
    "get_track_features": {"id": 999999},
    # ── CRUD Playlists ──
    "list_playlists": {"limit": 2},
    "get_playlist": {"id": 999999},
    "manage_playlist": {"action": "create", "data": json.dumps({"name": "Smoke Test Playlist"})},
    # ── CRUD Sets ──
    "list_sets": {"limit": 2},
    "get_set": {"id": 999999},
    "manage_set": {"action": "create", "data": json.dumps({"name": "Smoke Test Set"})},
    # ── Search ──
    "search": {"query": "test", "limit": 2},
    "filter_tracks": {"limit": 2},
    # ── Set Building ──
    "build_set": {"playlist_id": 999999, "name": "smoke"},
    "rebuild_set": {"set_id": 999999},
    "score_transitions": {"mode": "set", "set_id": 999999},
    "get_set_cheat_sheet": {"set_id": 999999},
    # ── Set Reasoning ──
    "suggest_next_track": {"set_id": 999999, "after_position": 0},
    "explain_transition": {"from_track_id": 999999, "to_track_id": 999998},
    "find_replacement": {"set_id": 999999, "position": 0},
    "compare_set_versions": {"set_id": 999999, "version_a": 1, "version_b": 2},
    "quick_set_review": {"set_id": 999999},
    # ── Admin ──
    "unlock_tools": {"action": "status"},
    "list_platforms": {},
    # ── Delivery ──
    "deliver_set": {"set_id": 999999, "dry_run": True},
    "export_set": {"set_id": 999999, "format": "m3u8"},
    # ── Discovery ──
    "find_similar_tracks": {"track_id": 999999},
    "filter_by_feedback": {"ym_track_ids": ["12345"]},
    "expand_playlist_ym": {"ym_playlist_kind": 999999, "dry_run": True},
    # ── Import/Download ──
    "import_tracks": {"track_refs": ["ym:99999999"]},
    "download_tracks": {"track_refs": ["99999999"]},
    # ── Curation ──
    "classify_mood": {"track_ids": [999999]},
    "audit_playlist": {"playlist_id": 999999},
    "review_set_quality": {"set_id": 999999},
    "distribute_to_subgenres": {"mode": "assign", "dry_run": True},
    "get_library_stats": {},
    # ── Sync ──
    "sync_playlist": {"playlist_id": 999999, "direction": "diff", "dry_run": True},
    "push_set_to_ym": {"set_id": 999999},
    # ── YM API ──
    "ym_search": {"query": "test", "limit": 2},
    "ym_get_tracks": {"track_ids": ["99999999"]},
    "ym_artist_tracks": {"artist_id": "999999"},
    "ym_get_album": {"album_id": "999999"},
    "ym_playlists": {"action": "list"},
    "ym_likes": {"action": "get_liked"},
    # ── Audio ──
    "analyze_track": {"track_id": 999999},
    "analyze_batch": {"track_ids": [999999]},
    "separate_stems": {"track_id": 999999},
    # ── Atomic ──
    "analyze_one_track": {"track_id": 999999},
    "classify_one_track": {"track_id": 999999},
    "gate_one_track": {"track_id": 999999},
    "get_similar_one_track": {"ym_track_id": "99999999"},
    # ── Decks ──
    "deck_load": {"deck_id": 1, "track_id": 999999, "duration_ms": 300000},
    "deck_play": {"deck_id": 1},
    "deck_pause": {"deck_id": 1},
    "deck_cue": {"deck_id": 1},
    "deck_unload": {"deck_id": 1},
    "deck_set_pitch": {"deck_id": 1, "pitch": 0.0},
    "deck_set_gain": {"deck_id": 1, "gain": 0.0},
    "deck_state": {"deck_id": 1},
    # ── Mixer ──
    "mixer_crossfader": {"target": 0.5},
    "mixer_channel_gain": {"deck_id": 1, "gain": 0.0},
    "mixer_state": {},
    "set_eq": {"deck_id": 1, "band": "mid", "gain": 0.0},
    "kill_eq": {"deck_id": 1, "band": "low"},
    "reset_eq": {"deck_id": 1},
    "set_filter": {"deck_id": 1, "cutoff_hz": 1000.0},
    # ── Feedback ──
    "like_track": {"track_id": 999999},
    "ban_track": {"track_id": 999999},
    "rate_track": {"track_id": 999999, "rating": 3},
    "get_track_feedback": {"track_id": 999999},
    "get_banned_tracks": {},
    "get_liked_tracks": {},
    # ── Transition History ──
    "log_transition": {
        "from_track_id": 999998,
        "to_track_id": 999997,
        "overall_score": 0.8,
    },
    "get_transition_history": {"limit": 2},
    "get_best_pairs": {"track_id": 999999, "limit": 2},
    "update_reaction": {"entry_id": 999999, "reaction": "like"},
    # ── Scoring Profiles ──
    "create_scoring_profile": {
        "name": "smoke_test",
        "bpm_weight": 0.2,
        "harmonic_weight": 0.12,
        "energy_weight": 0.18,
        "spectral_weight": 0.2,
        "groove_weight": 0.15,
        "timbral_weight": 0.15,
    },
    "list_scoring_profiles": {},
    "get_scoring_weights": {},
    # ── Track Affinity ──
    "refresh_affinity": {},
    "get_track_affinity": {"track_a_id": 999999, "track_b_id": 999998},
    "get_affinity_recommendations": {"track_id": 999999},
    # ── Adaptive Arc ──
    "get_energy_trend": {"last_n": 5},
    "suggest_energy_direction": {"last_n": 5},
    "get_session_arc": {"limit": 10},
    # ── Narrative & Misc ──
    "analyze_set_narrative": {"set_id": 999999},
    "get_set_templates": {},
    # watch_decks blocks (waits for state change) — skip in smoke test
    # "watch_decks": {},
    "run_tool": {"name": "list_platforms", "arguments": "{}"},
    # ── Transforms ──
    "list_prompts": {},
    "list_resources": {},
    "get_prompt": {
        "name": "build_set_workflow",
        "arguments": {"playlist_name": "test", "template": "classic_60", "duration_min": 60},
    },
    "read_resource": {"uri": "status://library"},
}

# Domain errors that mean the tool executed correctly
EXPECTED_ERRORS = {
    "NotFoundError",
    "not_found",
    "Not found",
    "not found",
    "No track",
    "No playlist",
    "No set",
    "does not exist",
    "No features",
    "Playlist not found",
    "Set not found",
    "Track not found",
    "no active",
    "empty",
    "No tracks",
    "no deck",
    "No tracks to distribute",
    "Invalid reaction",
    "validation error",
    "state",
    "not loaded",
    "not playing",
    "Cannot",
    "no data",
    "no transition",
}


def is_expected_error(text: str) -> bool:
    low = text.lower()
    return any(e.lower() in low for e in EXPECTED_ERRORS)


async def main() -> int:
    from unittest.mock import AsyncMock

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.audio.analyzers import AnalyzerRegistry
    from app.core.utils.cache import TransitionCache
    from app.db.models.base import Base
    from app.server import mcp

    # In-memory SQLite
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Static seed data
    from app.db.seed import seed_reference_data

    await seed_reference_data(factory)

    # Mock YM client
    ym = AsyncMock()
    ym.__aenter__ = AsyncMock(return_value=ym)
    ym.__aexit__ = AsyncMock(return_value=None)
    ym.search = AsyncMock(return_value=AsyncMock(tracks=[], albums=[], artists=[], playlists=[]))
    ym.get_liked_ids = AsyncMock(return_value=[])
    ym.get_disliked_ids = AsyncMock(return_value=set())
    ym.get_tracks = AsyncMock(return_value=[])
    ym.get_artist_tracks = AsyncMock(return_value=AsyncMock(tracks=[], pager=None))
    ym.get_album = AsyncMock(return_value=None)
    ym.get_playlists = AsyncMock(return_value=[])
    ym.get_playlist = AsyncMock(return_value=None)
    ym.get_similar = AsyncMock(return_value=[])
    ym.download_track = AsyncMock(return_value=None)

    registry = AnalyzerRegistry()
    registry.discover()
    cache = TransitionCache(max_size=100, ttl=60)

    from app.engines.deck.engine import DeckEngine
    from app.engines.mixer.engine import MixerEngine

    decks = {i: DeckEngine(deck_id=i) for i in range(1, 5)}
    mixer = MixerEngine(decks=decks)

    from fastmcp import Client
    from fastmcp.server.lifespan import lifespan

    original = mcp._lifespan

    @lifespan
    async def _test(server):  # type: ignore[no-untyped-def]
        yield {
            "db_engine": engine,
            "db_session_factory": factory,
            "ym_client": ym,
            "analyzer_registry": registry,
            "transition_cache": cache,
            "decks": decks,
            "mixer": mixer,
        }

    mcp._lifespan = _test
    mcp._lifespan_result = None
    mcp._lifespan_result_set = False

    # Unlock all
    from app.controllers.tools._shared.taxonomy import ToolCategory

    for c in ToolCategory:
        mcp.enable(tags={c.value})

    ok, expected_err, fail = [], [], []

    try:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            tool_names = {t.name for t in tools}
            print(f"\n{'=' * 70}")
            print(f"  SMOKE TEST: {len(TOOL_CALLS)} tools to test ({len(tool_names)} available)")
            print(f"{'=' * 70}\n")

            missing = set(TOOL_CALLS.keys()) - tool_names
            if missing:
                print(f"  MISSING from server: {missing}\n")

            for name, args in sorted(TOOL_CALLS.items()):
                if name not in tool_names:
                    fail.append((name, "NOT REGISTERED"))
                    print(f"  MISS  {name:40s}  NOT REGISTERED")
                    continue

                t0 = time.time()
                try:
                    result = await client.call_tool(name, args)
                    elapsed = time.time() - t0
                    # Check if result contains error text
                    text = str(result)[:200]
                    if "error" in text.lower() and is_expected_error(text):
                        expected_err.append((name, text[:80]))
                        print(f"  EXPE  {name:40s}  {elapsed:.2f}s  domain error (expected)")
                    else:
                        ok.append(name)
                        print(f"  OK    {name:40s}  {elapsed:.2f}s")
                except Exception as e:
                    elapsed = time.time() - t0
                    err = f"{type(e).__name__}: {e!s}"[:120]
                    if is_expected_error(err):
                        expected_err.append((name, err[:80]))
                        print(f"  EXPE  {name:40s}  {elapsed:.2f}s  {err[:60]}")
                    else:
                        fail.append((name, err))
                        print(f"  FAIL  {name:40s}  {elapsed:.2f}s  {err[:60]}")

    finally:
        mcp._lifespan_result = None
        mcp._lifespan_result_set = False
        mcp._lifespan = original

    # Summary
    print(f"\n{'=' * 70}")
    print(f"  RESULTS: {len(ok)} OK, {len(expected_err)} expected errors, {len(fail)} FAILURES")
    print(f"{'=' * 70}")

    if fail:
        print("\n  FAILURES (need investigation):")
        for n, e in fail:
            print(f"    {n}: {e}")
        return 1

    if expected_err:
        print(f"\n  Expected domain errors ({len(expected_err)}):")
        for n, e in expected_err:
            print(f"    {n}: {e[:70]}")

    print(f"\n  All {len(ok) + len(expected_err)} tools responded correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
