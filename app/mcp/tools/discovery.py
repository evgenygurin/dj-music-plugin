"""Discovery, filtering & expansion tools (3 tools, tag: discovery).

Thin wrappers calling DiscoveryService via Depends().
Tools:
- find_similar_tracks: find similar via YM API with declarative filters
- filter_by_feedback: apply liked/disliked gate to a list of YM track IDs
- expand_playlist_ym: high-level orchestrator (seeds → similar → filter → add)
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.core.parsing import ensure_list
from app.mcp.dependencies import get_discovery_service
from app.services.discovery_service import DiscoveryService

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
    genre_filter: Any = None,
    genre_blacklist: Any = None,
    exclude_patterns: Any = None,
    svc: DiscoveryService = Depends(get_discovery_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Find similar tracks via YM API with declarative filters.

    strategy: ym (default). genre_filter: whitelist. genre_blacklist: blacklist.
    exclude_patterns: title keywords to skip (default: remix, edit, live, ...).
    """
    genre_filter_list = ensure_list(genre_filter) or None
    genre_blacklist_list = ensure_list(genre_blacklist) or None
    exclude_patterns_list = ensure_list(exclude_patterns) or None

    if strategy == "llm" and ctx:
        return await _find_similar_llm(
            track_id,
            limit,
            genre_filter_list,
            genre_blacklist_list,
            exclude_patterns_list,
            svc,
            ctx,
        )

    if strategy != "ym":
        return {
            "track_id": track_id,
            "strategy": strategy,
            "similar": [],
            "message": f"Strategy '{strategy}' requires: ym or llm",
        }

    if ctx:
        await ctx.info(f"Finding similar tracks for track {track_id}...")

    return await svc.find_similar_ym(
        track_id=track_id,
        limit=limit,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
        genre_filter_list=genre_filter_list,
        genre_blacklist_list=genre_blacklist_list,
        exclude_patterns_list=exclude_patterns_list,
    )


async def _find_similar_llm(
    track_id: int,
    limit: int,
    genre_filter_list: list[str] | None,
    genre_blacklist_list: list[str] | None,
    exclude_patterns_list: list[str] | None,
    svc: DiscoveryService,
    ctx: Context,
) -> dict[str, Any]:
    """LLM-assisted similar track discovery — ctx.sample() is MCP-specific."""
    track = await svc._tracks.get_by_id(track_id)
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

    return await svc.find_similar_llm(
        track_id=track_id,
        queries=queries,
        limit=limit,
        genre_filter_list=genre_filter_list,
        genre_blacklist_list=genre_blacklist_list,
        exclude_patterns_list=exclude_patterns_list,
    )


# ── 2. filter_by_feedback ────────────────────────────


@tool(
    tags={"discovery"},
    annotations={"readOnlyHint": True, "openWorldHint": True},
)
async def filter_by_feedback(
    ym_track_ids: Any = None,
    svc: DiscoveryService = Depends(get_discovery_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Apply liked/disliked feedback gate to YM track IDs.

    Returns categorized IDs: passed (unknown), blocked (disliked), boosted (liked).
    Claude decides what to do with each category.
    """
    ym_track_ids = ensure_list(ym_track_ids)
    if not ym_track_ids:
        raise ToolError("ym_track_ids required")

    # Check session cache first (MCP-specific)
    liked_set: set[str] | None = None
    disliked_set: set[str] | None = None
    if ctx:
        cached_liked = await ctx.get_state("ym_liked_ids")
        cached_disliked = await ctx.get_state("ym_disliked_ids")
        if cached_liked is not None and cached_disliked is not None:
            await ctx.info("Using cached feedback (session state)")
            liked_set = set(cached_liked)
            disliked_set = set(cached_disliked)

    if liked_set is None or disliked_set is None:
        if ctx:
            await ctx.info("Fetching liked/disliked from YM API...")
        liked_set, disliked_set = await svc.get_feedback_sets()
        if ctx:
            await ctx.set_state("ym_liked_ids", list(liked_set))
            await ctx.set_state("ym_disliked_ids", list(disliked_set))

    return await svc.filter_by_feedback(
        ym_track_ids=list(ym_track_ids),
        liked_set=liked_set,
        disliked_set=disliked_set,
    )


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
    genre_filter: Any = None,
    genre_blacklist: Any = None,
    exclude_patterns: Any = None,
    min_duration_ms: int | None = None,
    max_duration_ms: int | None = None,
    use_feedback: bool = True,
    dry_run: bool = False,
    svc: DiscoveryService = Depends(get_discovery_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Expand YM playlist with similar tracks. Declarative filters for genre, duration, feedback.

    One-call orchestrator: fetches seeds → finds similar → filters → adds to playlist.
    Or use find_similar_tracks + filter_by_feedback + ym_playlists separately for full control.
    """
    genre_filter_list = ensure_list(genre_filter) or None
    genre_blacklist_list = ensure_list(genre_blacklist) or None
    exclude_patterns_list = ensure_list(exclude_patterns) or None

    if ctx:
        await ctx.info("Fetching playlist tracks...")

    return await svc.expand_playlist_ym(
        ym_playlist_kind=ym_playlist_kind,
        target_count=target_count,
        genre_filter_list=genre_filter_list,
        genre_blacklist_list=genre_blacklist_list,
        exclude_patterns_list=exclude_patterns_list,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
        use_feedback=use_feedback,
        dry_run=dry_run,
    )
