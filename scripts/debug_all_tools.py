"""Debug all FastMCP tools — list, call each with minimal args, log results.

Usage:
    .venv/bin/python scripts/debug_all_tools.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import traceback

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Suppress noisy loggers
for name in ("httpx", "httpcore", "sqlalchemy", "fastmcp", "app"):
    logging.getLogger(name).setLevel(logging.WARNING)

# ── Minimal call args per tool ──
# Each tool gets the simplest possible args to exercise its schema + DI chain.
# We expect clean errors (ToolError for "not found") — NOT crashes or schema failures.
TOOL_ARGS: dict[str, dict] = {
    # ── Core: Tracks ──
    "list_tracks": {"limit": 2},
    "get_track": {"id": 1},
    "manage_tracks": {"action": "create", "data": {"title": "Debug Track", "duration_ms": 180000}},
    "get_track_features": {"id": 1},
    # ── Core: Playlists ──
    "list_playlists": {"limit": 2},
    "get_playlist": {"id": 1},
    "manage_playlist": {"action": "create", "data": {"name": "Debug Playlist"}},
    # ── Core: Sets ──
    "list_sets": {"limit": 2},
    "get_set": {"id": 1},
    "manage_set": {"action": "create", "data": {"name": "Debug Set"}},
    # ── Search ──
    "search": {"query": "test", "entity": "tracks", "limit": 2},
    "filter_tracks": {"limit": 2},
    # ── Set Building ──
    "build_set": {"playlist_id": 1, "name": "Debug Build", "algorithm": "greedy"},
    "rebuild_set": {"set_id": 1, "algorithm": "greedy"},
    "score_transitions": {"mode": "set", "set_id": 1},
    "get_set_cheat_sheet": {"set_id": 1},
    # ── Set Reasoning ──
    "suggest_next_track": {"set_id": 1, "after_position": 0},
    "explain_transition": {"from_track_id": 1, "to_track_id": 2},
    "find_replacement": {"set_id": 1, "position": 0},
    "compare_set_versions": {"set_id": 1},
    "quick_set_review": {"set_id": 1},
    # ── Admin ──
    "unlock_tools": {"action": "status"},
    "list_platforms": {},
    # ── Delivery ──
    "deliver_set": {"set_id": 1, "dry_run": True},
    "export_set": {"set_id": 1, "format": "m3u8"},
    # ── Discovery ──
    "find_similar_tracks": {"track_id": 1, "strategy": "ym", "limit": 2},
    "expand_playlist_ym": {"ym_playlist_kind": 1, "dry_run": True},
    "filter_by_feedback": {"ym_track_ids": ["12345"]},
    "import_tracks": {"track_refs": ["12345"]},
    "download_tracks": {"track_refs": ["12345"]},
    # ── Curation ──
    "classify_mood": {"track_ids": [1]},
    "audit_playlist": {"playlist_id": 1},
    "review_set_quality": {"set_id": 1},
    "distribute_to_subgenres": {"dry_run": True},
    "get_library_stats": {},
    # ── Sync ──
    "sync_playlist": {"playlist_id": 1, "direction": "diff", "dry_run": True},
    "push_set_to_ym": {"set_id": 1},
    # ── YM API ──
    "ym_search": {"query": "test", "type": "tracks", "limit": 2},
    "ym_get_tracks": {"track_ids": ["12345"]},
    "ym_artist_tracks": {"artist_id": "12345"},
    "ym_get_album": {"album_id": "12345"},
    "ym_playlists": {"action": "list"},
    "ym_likes": {"action": "get_liked"},
    # ── Audio ──
    "analyze_track": {"track_id": 1},
    "analyze_batch": {"track_ids": [1]},
    "separate_stems": {"track_id": 1},
    # ── Atomic ──
    "analyze_one_track": {"track_id": 1},
    "classify_one_track": {"track_id": 1},
    "gate_one_track": {"track_id": 1},
    "get_similar_one_track": {"ym_track_id": "12345"},
    # ── Decks (param: deck_id, not deck) ──
    "deck_load": {"deck_id": 1, "track_id": 1, "duration_ms": 180000},
    "deck_play": {"deck_id": 1},
    "deck_pause": {"deck_id": 1},
    "deck_cue": {"deck_id": 1},
    "deck_unload": {"deck_id": 1},
    "deck_set_pitch": {"deck_id": 1, "pitch": 0.0},
    "deck_set_gain": {"deck_id": 1, "gain": 0.0},
    "deck_state": {"deck_id": 1},
    # ── Mixer (param: deck_id, target, gain) ──
    "mixer_crossfader": {"target": 0.5},
    "mixer_channel_gain": {"deck_id": 1, "gain": 0.0},
    "mixer_state": {},
    "set_eq": {"deck_id": 1, "band": "mid", "gain": 0.0},
    "kill_eq": {"deck_id": 1, "band": "mid"},
    "reset_eq": {"deck_id": 1},
    "set_filter": {"deck_id": 1, "cutoff_hz": 1000.0},
    # ── Monitoring ──
    "watch_decks": {},
    # ── Memory / Feedback ──
    "log_transition": {"from_track_id": 1, "to_track_id": 2},
    "get_transition_history": {},
    "get_best_pairs": {"track_id": 1},
    "update_reaction": {"entry_id": 1, "reaction": "like"},
    "like_track": {"track_id": 1},
    "ban_track": {"track_id": 1},
    "rate_track": {"track_id": 1, "rating": 4},
    "get_track_feedback": {"track_id": 1},
    "get_banned_tracks": {},
    "get_liked_tracks": {},
    # ── Affinity (refresh_affinity has no params, get_track_affinity needs track_a_id + track_b_id) ──
    "refresh_affinity": {},
    "get_track_affinity": {"track_a_id": 1, "track_b_id": 2},
    "get_affinity_recommendations": {"track_id": 1},
    # ── Scoring Profile ──
    "create_scoring_profile": {"name": "debug-profile"},
    "list_scoring_profiles": {},
    "get_scoring_weights": {},
    # ── Set Narrative ──
    "analyze_set_narrative": {"set_id": 1},
    # ── Sets Meta ──
    "get_set_templates": {},
    # ── Adaptive Arc (no set_id — uses last_n) ──
    "get_energy_trend": {"last_n": 5},
    "suggest_energy_direction": {"last_n": 5},
    "get_session_arc": {},
    # ── Run Tool (param: name, not tool_name) ──
    "run_tool": {"name": "list_platforms"},
}


def _extract_text(result) -> str:
    """Best-effort text extraction from CallToolResult."""
    if hasattr(result, "data") and isinstance(result.data, dict):
        return json.dumps(result.data, ensure_ascii=False, default=str)[:500]
    content = getattr(result, "content", result)
    if isinstance(content, list) and len(content) > 0:
        block = content[0]
        text = getattr(block, "text", None) or str(block)
        return text[:500]
    return str(result)[:500]


async def main() -> None:
    from unittest.mock import AsyncMock

    from fastmcp import Client
    from fastmcp.server.lifespan import lifespan
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from app.db.models.base import Base
    from app.server import mcp

    # ── Setup in-memory DB ──
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    def _pragma(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    event.listen(engine.sync_engine, "connect", _pragma)

    # Force all model imports so Base.metadata.create_all creates all tables
    import app.db.models.audio
    import app.db.models.export
    import app.db.models.ingestion
    import app.db.models.key
    import app.db.models.library
    import app.db.models.playlist
    import app.db.models.scoring_profile
    import app.db.models.set
    import app.db.models.track
    import app.db.models.track_affinity
    import app.db.models.track_feedback
    import app.db.models.transition
    import app.db.models.transition_history  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    # ── Seed reference data ──
    from app.core.constants import CAMELOT_KEYS
    from app.db.models.key import Key

    async with factory() as session:
        for code, (camelot, name) in CAMELOT_KEYS.items():
            mode = 1 if camelot.endswith("B") else 0
            pitch_class = code % 12
            session.add(
                Key(key_code=code, pitch_class=pitch_class, mode=mode, name=name, camelot=camelot)
            )
        await session.commit()

    # ── Mock YM client ──
    ym_mock = AsyncMock()
    ym_mock.__aenter__.return_value = ym_mock
    ym_mock.__aexit__.return_value = None
    ym_mock.search = AsyncMock(
        return_value=AsyncMock(tracks=[], albums=[], artists=[], playlists=[])
    )
    ym_mock.get_liked_ids = AsyncMock(return_value=[])
    ym_mock.get_disliked_ids = AsyncMock(return_value=set())
    ym_mock.get_tracks = AsyncMock(return_value=[])
    ym_mock.get_playlist = AsyncMock(return_value=AsyncMock(kind=42, title="Debug", revision=1))
    ym_mock.get_playlist_tracks = AsyncMock(return_value=[])
    ym_mock.add_tracks_to_playlist = AsyncMock(return_value={"revision": 2})
    ym_mock.resolve_track_ids_with_albums = AsyncMock(side_effect=lambda ids: ids)
    ym_mock.get_similar = AsyncMock(return_value=[])
    ym_mock.get_album = AsyncMock(return_value=None)
    ym_mock.get_artist_tracks = AsyncMock(return_value=AsyncMock(tracks=[], pager=None))
    ym_mock.list_playlists = AsyncMock(return_value=[])
    ym_mock.close = AsyncMock()
    ym_mock.download_track = AsyncMock(return_value=0)

    from app.audio.analyzers import AnalyzerRegistry
    from app.core.utils.cache import TransitionCache

    registry = AnalyzerRegistry()
    registry.discover()
    cache = TransitionCache(max_size=100, ttl=60)

    original_lifespan = mcp._lifespan

    @lifespan
    async def _test_lifespan(server):
        yield {
            "db_engine": engine,
            "db_session_factory": factory,
            "ym_client": ym_mock,
            "analyzer_registry": registry,
            "transition_cache": cache,
        }

    mcp._lifespan = _test_lifespan
    mcp._lifespan_result = None
    mcp._lifespan_result_set = False

    results: list[dict] = []

    try:
        async with Client(mcp) as client:
            # ── Phase 1: List all tools ──
            print("=" * 70)
            print("PHASE 1: Listing all registered tools")
            print("=" * 70)

            all_tools = await client.list_tools()
            tool_names = sorted(t.name for t in all_tools)
            print(f"\nTotal tools registered: {len(tool_names)}")
            for i, name in enumerate(tool_names, 1):
                print(f"  {i:3d}. {name}")

            # Check which tools from TOOL_ARGS are missing
            registered = set(tool_names)
            expected = set(TOOL_ARGS.keys())
            missing_from_server = expected - registered
            extra_in_server = registered - expected

            if missing_from_server:
                print(
                    f"\n⚠ Tools in TOOL_ARGS but NOT registered on server ({len(missing_from_server)}):"
                )
                for n in sorted(missing_from_server):
                    print(f"  - {n}")

            if extra_in_server:
                print(f"\n⚠ Tools on server but NOT in TOOL_ARGS ({len(extra_in_server)}):")
                for n in sorted(extra_in_server):
                    print(f"  - {n}")

            # ── Phase 2: Check tool metadata ──
            print("\n" + "=" * 70)
            print("PHASE 2: Checking tool metadata (title, tags, annotations)")
            print("=" * 70)

            metadata_warnings = []
            for t in all_tools:
                issues = []
                if not getattr(t, "title", None) and not getattr(t, "description", None):
                    issues.append("no title or description")
                desc = getattr(t, "description", "") or ""
                if len(desc) > 300:
                    issues.append(f"description too long ({len(desc)} chars)")
                if not getattr(t, "inputSchema", None):
                    issues.append("no inputSchema")
                if issues:
                    metadata_warnings.append({"tool": t.name, "issues": issues})

            if metadata_warnings:
                print(f"\nMetadata warnings ({len(metadata_warnings)}):")
                for w in metadata_warnings:
                    print(f"  {w['tool']}: {', '.join(w['issues'])}")
            else:
                print("\n✓ All tool metadata looks OK")

            # ── Phase 3: Call each tool ──
            print("\n" + "=" * 70)
            print("PHASE 3: Calling each tool with minimal args")
            print("=" * 70)

            # Unlock all categories first
            try:
                await client.call_tool("unlock_tools", {"action": "unlock", "category": "all"})
                print("\n✓ All tool categories unlocked")
            except Exception as e:
                print(f"\n✗ Failed to unlock tools: {e}")

            # Re-list tools after unlock — client should see newly enabled tools
            all_tools_after = await client.list_tools()
            tool_names_after = sorted(t.name for t in all_tools_after)
            new_tools = set(tool_names_after) - set(tool_names)
            registered = set(tool_names_after)
            print(f"  Tools after unlock: {len(tool_names_after)} (+{len(new_tools)} new)")
            if new_tools:
                for n in sorted(new_tools):
                    print(f"    + {n}")

            # Call each tool
            total = len(TOOL_ARGS)
            ok_count = 0
            error_count = 0
            warn_count = 0

            for i, (tool_name, args) in enumerate(sorted(TOOL_ARGS.items()), 1):
                if tool_name not in registered:
                    results.append(
                        {
                            "tool": tool_name,
                            "status": "MISSING",
                            "error": "Not registered on server",
                            "traceback": "",
                        }
                    )
                    print(f"  [{i:3d}/{total}] {tool_name:40s} MISSING")
                    error_count += 1
                    continue

                t0 = time.time()
                try:
                    result = await client.call_tool(tool_name, args)
                    elapsed = time.time() - t0
                    text = _extract_text(result)

                    # Check if result indicates an error
                    is_error = getattr(result, "isError", False)
                    if is_error:
                        results.append(
                            {
                                "tool": tool_name,
                                "status": "TOOL_ERROR",
                                "error": text,
                                "elapsed": f"{elapsed:.2f}s",
                                "traceback": "",
                            }
                        )
                        print(
                            f"  [{i:3d}/{total}] {tool_name:40s} TOOL_ERROR ({elapsed:.2f}s): {text[:80]}"
                        )
                        warn_count += 1
                    else:
                        results.append(
                            {
                                "tool": tool_name,
                                "status": "OK",
                                "elapsed": f"{elapsed:.2f}s",
                                "preview": text[:120],
                            }
                        )
                        print(f"  [{i:3d}/{total}] {tool_name:40s} OK ({elapsed:.2f}s)")
                        ok_count += 1

                except Exception as e:
                    elapsed = time.time() - t0
                    tb = traceback.format_exc()
                    error_type = type(e).__name__
                    results.append(
                        {
                            "tool": tool_name,
                            "status": "EXCEPTION",
                            "error": f"{error_type}: {e}",
                            "elapsed": f"{elapsed:.2f}s",
                            "traceback": tb,
                        }
                    )
                    print(
                        f"  [{i:3d}/{total}] {tool_name:40s} EXCEPTION ({elapsed:.2f}s): {error_type}: {str(e)[:80]}"
                    )
                    error_count += 1

            # ── Summary ──
            print("\n" + "=" * 70)
            print("SUMMARY")
            print("=" * 70)
            print(f"  Total tools tested:  {total}")
            print(f"  OK:                  {ok_count}")
            print(f"  Tool errors (warn):  {warn_count}")
            print(f"  Exceptions (error):  {error_count}")

            # ── Write JSON report ──
            report = {
                "total_registered": len(tool_names),
                "total_tested": total,
                "ok": ok_count,
                "tool_errors": warn_count,
                "exceptions": error_count,
                "missing_from_server": sorted(missing_from_server),
                "extra_in_server": sorted(extra_in_server),
                "metadata_warnings": metadata_warnings,
                "results": results,
            }
            report_path = "scripts/debug_tools_report.json"
            with open(report_path, "w") as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            print(f"\n  Full report saved to: {report_path}")

    finally:
        mcp._lifespan_result = None
        mcp._lifespan_result_set = False
        mcp._lifespan = original_lifespan
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
