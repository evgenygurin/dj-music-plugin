"""Discovery, filtering & expansion tools (5 tools, tag: discovery).

Tools:
- find_similar_tracks: find similar via YM API with declarative filters
- filter_by_feedback: apply liked/disliked gate to a list of YM track IDs
- expand_playlist_ym: high-level orchestrator (seeds → similar → filter → add)
- import_tracks: import YM track IDs into local DB
- download_tracks: download MP3 from YM (stub — future)
"""

from __future__ import annotations

import random
from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from sqlalchemy import select

from app.config import settings
from app.mcp.dependencies import get_db_session, get_ym_client
from app.models.track import TrackExternalId
from app.ym.client import YandexMusicClient

# ── Helpers ──────────────────────────────────────────


def _is_excluded(title: str, patterns: list[str] | None = None) -> bool:
    """Check if track title matches any exclude pattern."""
    lower = title.lower()
    check = patterns or settings.discovery_bad_version_words.split(",")
    return any(p.strip() in lower for p in check)


def _genre_ok(
    albums: list[dict[str, Any]],
    whitelist: list[str] | None = None,
    blacklist: list[str] | None = None,
) -> bool:
    """Check album genre against whitelist or blacklist.

    - whitelist: accept ONLY these genres (e.g. ["techno"])
    - blacklist: reject these genres (default from settings)
    - both None: use settings.discovery_bad_genres as blacklist
    """
    if not albums:
        return True  # no album info = accept
    genre = (albums[0].get("genre") or "").lower()
    if not genre:
        return True
    if whitelist:
        return genre in [g.lower() for g in whitelist]
    bad = blacklist or settings.discovery_bad_genres.split(",")
    return genre not in [b.strip() for b in bad]


def _ym_track_dict(track: Any) -> dict[str, Any]:
    """Compact summary of a YM track for tool output."""
    artists = ", ".join(a.get("name", "?") for a in (track.artists or [])) or "Unknown"
    albums = track.albums or []
    return {
        "ym_id": track.id,
        "title": track.title,
        "artists": artists,
        "duration_ms": track.duration_ms,
        "album_id": str(albums[0].get("id", "")) if albums else "",
        "album_genre": albums[0].get("genre", "") if albums else "",
    }


# ── 1. find_similar_tracks ──────────────────────────


@tool(
    tags={"discovery"},
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def find_similar_tracks(
    track_id: int,
    strategy: str = "ym",
    limit: int = 20,
    min_duration_ms: int | None = None,
    max_duration_ms: int | None = None,
    genre_filter: list[str] | None = None,
    genre_blacklist: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Find similar tracks via YM API with declarative filters.

    strategy: ym (default). genre_filter: whitelist. genre_blacklist: blacklist.
    exclude_patterns: title keywords to skip (default: remix, edit, live, ...).
    """
    if strategy == "llm" and ctx:
        # LLM-assisted: use ctx.sample() to generate search queries
        async with get_db_session() as session:
            from app.repositories.track import TrackRepository

            track = await TrackRepository(session).get_by_id(track_id)
            if not track:
                raise ToolError(f"Track {track_id} not found")

        try:
            from pydantic import BaseModel

            class SearchQueries(BaseModel):
                queries: list[str]

            result = await ctx.sample(
                f"Generate {limit} Yandex Music search queries to find techno tracks "
                f"similar to '{track.title}'. Return ONLY track/artist names, no explanations.",
                result_type=SearchQueries,
            )
            queries = result.result.queries if result.result else []
        except Exception as e:
            return {
                "track_id": track_id,
                "strategy": "llm",
                "similar": [],
                "message": f"LLM sampling failed: {e}. Configure ANTHROPIC_API_KEY for fallback.",
            }

        # Search YM for each query
        all_results = []
        for q in queries[:limit]:
            try:
                sr = await ym.search(q, type="tracks", limit=3)
                for t in sr.tracks:
                    if not _genre_ok(
                        t.albums or [], whitelist=genre_filter, blacklist=genre_blacklist
                    ):
                        continue
                    if _is_excluded(t.title, exclude_patterns):
                        continue
                    all_results.append(_ym_track_dict(t))
            except Exception:
                continue

        # Dedup
        seen: set[str] = set()
        deduped = []
        for r in all_results:
            if r["ym_id"] not in seen:
                seen.add(r["ym_id"])
                deduped.append(r)

        return {
            "track_id": track_id,
            "track_title": track.title,
            "strategy": "llm",
            "queries_used": queries,
            "total_raw": len(all_results),
            "after_filter": len(deduped),
            "similar": deduped[:limit],
        }

    if strategy not in ("ym",):
        return {
            "track_id": track_id,
            "strategy": strategy,
            "similar": [],
            "message": f"Strategy '{strategy}' requires: ym or llm",
        }

    # Find YM ID for this track
    async with get_db_session() as session:
        track = await TrackRepository(session).get_by_id(track_id)
        if not track:
            raise ToolError(f"Track {track_id} not found")

        stmt = select(TrackExternalId).where(
            TrackExternalId.track_id == track_id,
            TrackExternalId.platform == "yandex_music",
        )
        result = await session.execute(stmt)
        ext = result.scalar_one_or_none()

    ym_id = ext.external_id if ext else None

    # Fallback: search by title
    if not ym_id:
        if ctx:
            await ctx.info(f"No YM ID for track {track_id}, searching by title...")
        search_result = await ym.search(track.title, type="tracks", limit=1)
        if search_result.tracks:
            ym_id = search_result.tracks[0].id
        else:
            return {
                "track_id": track_id,
                "track_title": track.title,
                "strategy": "ym",
                "similar": [],
                "message": "Could not find this track on YM",
            }

    # Get similar from YM
    raw_similar = await ym.get_similar(ym_id)

    # Apply filters
    min_dur = min_duration_ms or settings.discovery_min_duration_ms
    max_dur = max_duration_ms or settings.discovery_max_duration_ms

    filtered = []
    for t in raw_similar:
        dur = t.duration_ms or 0
        if dur and (dur < min_dur or dur > max_dur):
            continue
        if _is_excluded(t.title, exclude_patterns):
            continue
        if not _genre_ok(t.albums or [], whitelist=genre_filter, blacklist=genre_blacklist):
            continue
        filtered.append(_ym_track_dict(t))
        if len(filtered) >= limit:
            break

    return {
        "track_id": track_id,
        "track_title": track.title,
        "strategy": "ym",
        "ym_id_used": ym_id,
        "total_raw": len(raw_similar),
        "after_filter": len(filtered),
        "similar": filtered,
    }


# ── 2. filter_by_feedback ────────────────────────────


@tool(
    tags={"discovery"},
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def filter_by_feedback(
    ym_track_ids: list[str],
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Apply liked/disliked feedback gate to YM track IDs.

    Returns categorized IDs: passed (unknown), blocked (disliked), boosted (liked).
    Claude decides what to do with each category.
    """
    if not ym_track_ids:
        raise ToolError("ym_track_ids required")

    # Cache feedback IDs in session state (avoids 2 API calls per invocation)
    liked_set: set[str] = set()
    disliked_set: set[str] = set()
    if ctx:
        cached_liked = await ctx.get_state("ym_liked_ids")
        cached_disliked = await ctx.get_state("ym_disliked_ids")
        if cached_liked is not None and cached_disliked is not None:
            liked_set = set(cached_liked)
            disliked_set = set(cached_disliked)
            await ctx.info("Using cached feedback (session state)")

    if not liked_set and not disliked_set:
        if ctx:
            await ctx.info("Fetching liked/disliked from YM API...")
        liked_raw = await ym.get_liked_ids()
        disliked_set = await ym.get_disliked_ids()
        liked_set = set(liked_raw)
        # Cache for subsequent calls in this session
        if ctx:
            await ctx.set_state("ym_liked_ids", list(liked_set))
            await ctx.set_state("ym_disliked_ids", list(disliked_set))

    result_passed: list[str] = []
    result_blocked: list[str] = []
    result_boosted: list[str] = []

    for tid in ym_track_ids:
        if tid in disliked_set:
            result_blocked.append(tid)
        elif tid in liked_set:
            result_boosted.append(tid)
        else:
            result_passed.append(tid)

    return {
        "total": len(ym_track_ids),
        "passed": result_passed,
        "blocked_disliked": result_blocked,
        "boosted_liked": result_boosted,
        "counts": {
            "passed": len(result_passed),
            "blocked": len(result_blocked),
            "boosted": len(result_boosted),
        },
    }


# ── 3. expand_playlist_ym ───────────────────────────


@tool(
    tags={"discovery"},
    annotations={"readOnlyHint": False, "openWorldHint": True},
    timeout=600.0,
    task=True,
)
async def expand_playlist_ym(
    ym_playlist_kind: int,
    target_count: int = 100,
    genre_filter: list[str] | None = None,
    genre_blacklist: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    min_duration_ms: int | None = None,
    max_duration_ms: int | None = None,
    use_feedback: bool = True,
    dry_run: bool = False,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Expand YM playlist with similar tracks. Declarative filters for genre, duration, feedback.

    One-call orchestrator: fetches seeds → finds similar → filters → adds to playlist.
    Or use find_similar_tracks + filter_by_feedback + ym_playlists separately for full control.
    """
    import time as _time

    _t0 = _time.monotonic()

    # 1. Fetch current playlist
    if ctx:
        await ctx.info("Fetching playlist tracks...")
    current = await ym.get_playlist_tracks(settings.ym_user_id, ym_playlist_kind)
    existing_ids = {t.id for t in current}
    need = max(0, target_count - len(current))

    if need == 0:
        return {
            "playlist_kind": ym_playlist_kind,
            "current_count": len(current),
            "target_count": target_count,
            "added": 0,
            "message": "Playlist already meets target count",
        }

    # 2. Select seeds
    max_seeds = min(len(current), settings.discovery_max_seeds)
    seeds = random.sample(current, max_seeds) if len(current) > max_seeds else list(current)

    # 3. Feedback gate (use session cache if available)
    disliked: set[str] = set()
    liked: set[str] = set()
    if use_feedback:
        if ctx:
            cached_liked = await ctx.get_state("ym_liked_ids")
            cached_disliked = await ctx.get_state("ym_disliked_ids")
            if cached_liked is not None and cached_disliked is not None:
                liked = set(cached_liked)
                disliked = set(cached_disliked)
                await ctx.info("Using cached feedback (session state)")
        if not liked and not disliked:
            if ctx:
                await ctx.info("Fetching feedback from YM API...")
            liked_raw = await ym.get_liked_ids()
            liked = set(liked_raw)
            disliked = await ym.get_disliked_ids()
            if ctx:
                await ctx.set_state("ym_liked_ids", list(liked))
                await ctx.set_state("ym_disliked_ids", list(disliked))

    # 4. Collect candidates
    min_dur = min_duration_ms or settings.discovery_min_duration_ms
    max_dur = max_duration_ms or settings.discovery_max_duration_ms
    candidates: list[dict[str, Any]] = []
    blocked_count = 0

    for i, seed in enumerate(seeds):
        if len(candidates) >= need:
            break
        if ctx:
            await ctx.report_progress(i, len(seeds))
            await ctx.info(f"Seed {i + 1}/{len(seeds)}: {seed.title}")

        try:
            raw_similar = await ym.get_similar(seed.id)
        except Exception:
            continue

        for t in raw_similar:
            if t.id in existing_ids:
                continue
            if any(c["ym_id"] == t.id for c in candidates):
                continue
            # Feedback gate
            if use_feedback and t.id in disliked:
                blocked_count += 1
                continue
            # Duration
            dur = t.duration_ms or 0
            if dur and (dur < min_dur or dur > max_dur):
                continue
            # Title patterns
            if _is_excluded(t.title, exclude_patterns):
                continue
            # Genre
            if not _genre_ok(t.albums or [], whitelist=genre_filter, blacklist=genre_blacklist):
                continue

            entry = _ym_track_dict(t)
            entry["is_liked"] = t.id in liked
            candidates.append(entry)

            if len(candidates) >= need:
                break

    if ctx:
        await ctx.report_progress(len(seeds), len(seeds))

    # 5. Dry run
    to_add = candidates[:need]

    if dry_run:
        return {
            "dry_run": True,
            "playlist_kind": ym_playlist_kind,
            "current_count": len(current),
            "target_count": target_count,
            "candidates_found": len(candidates),
            "would_add": len(to_add),
            "blocked_disliked": blocked_count,
            "seeds_used": min(len(seeds), len(seeds)),
            "candidates": to_add[:50],
        }

    # 6. Batch add
    playlist_info = await ym.get_playlist(settings.ym_user_id, ym_playlist_kind)
    revision = playlist_info.revision or 1
    added = 0
    batch_size = settings.discovery_batch_size

    for batch_start in range(0, len(to_add), batch_size):
        batch = to_add[batch_start : batch_start + batch_size]
        track_ids_batch = [
            f"{c['ym_id']}:{c['album_id']}" if c.get("album_id") else c["ym_id"] for c in batch
        ]
        try:
            result = await ym.add_tracks_to_playlist(ym_playlist_kind, track_ids_batch, revision)
            revision = result.get("revision", revision + 1)
            added += len(batch)
            if ctx:
                await ctx.info(f"Added batch: {added}/{len(to_add)}")
        except Exception as e:
            if ctx:
                await ctx.warning(f"Batch failed: {e}")
            break

    elapsed_ms = int((_time.monotonic() - _t0) * 1000)

    from fastmcp.tools.tool import ToolResult
    from mcp.types import TextContent

    data = {
        "playlist_kind": ym_playlist_kind,
        "before_count": len(current),
        "after_count": len(current) + added,
        "added": added,
        "seeds_used": len(seeds),
        "candidates_found": len(candidates),
        "blocked_disliked": blocked_count,
        "sample_tracks": to_add[:20],
    }

    return ToolResult(
        content=[
            TextContent(
                type="text", text=f"Added {added} tracks ({len(current)}→{len(current) + added})"
            )
        ],
        structured_content=data,
        meta={
            "execution_time_ms": elapsed_ms,
            "seeds_used": len(seeds),
            "ym_api_calls": len(seeds) + 2,
        },
    )
