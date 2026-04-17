"""Discovery, filtering & expansion tools (3 tools).

Thin wrappers calling :class:`DiscoveryService` via ``Depends()``.

``find_similar_tracks`` is tagged ``core`` so it appears in the default MCP ``tools/list``
(Cursor and similar clients snapshot tools on connect; discovery-only tools stay hidden
until ``unlock_tools``).

Tools:
- ``find_similar_tracks`` — platform API with declarative filters (+ optional LLM mode)
- ``filter_by_feedback`` — liked/disliked gate for platform track IDs
- ``expand_platform_playlist`` — high-level orchestrator (seeds → similar → filter → add)
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import BaseModel, Field

from app.controllers.dependencies import get_discovery_service
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    ANNOTATIONS_WRITE_OPEN_WORLD,
    ICON_DISCOVERY,
    TOOL_META,
    ToolCategory,
    ToolContext,
    ToolTimeout,
    map_domain_errors,
)
from app.controllers.tools._shared.llm_sampling import (
    format_sampling_unavailable_note,
    sample_structured,
)
from app.core.utils.parsing import ensure_list
from app.services.discovery_service import DiscoveryService

_log = logging.getLogger(__name__)


class _LLMSearchQueries(BaseModel):
    """Structured response schema for LLM similar-track query generation."""

    queries: list[str]


async def _find_similar_llm(
    track_id: int,
    limit: int,
    min_duration_ms: int | None,
    max_duration_ms: int | None,
    genre_filter_list: list[str] | None,
    genre_blacklist_list: list[str] | None,
    exclude_patterns_list: list[str] | None,
    svc: DiscoveryService,
    ctx: Context,
) -> dict[str, Any]:
    """LLM-assisted discovery; falls back to YM ``get_similar`` if sampling is unavailable."""
    track = await svc._tracks.get_by_id(track_id)
    if not track:
        raise ToolError(f"Track {track_id} not found")

    async def _ym_platform_fallback(note: str) -> dict[str, Any]:
        out = await svc.find_similar_ym(
            track_id=track_id,
            limit=limit,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
            genre_filter_list=genre_filter_list,
            genre_blacklist_list=genre_blacklist_list,
            exclude_patterns_list=exclude_patterns_list,
        )
        out["strategy_requested"] = "llm"
        out["sampling_note"] = note
        return out

    try:
        result = await sample_structured(
            ctx,
            f"Generate {limit} Yandex Music search queries to find techno tracks "
            f"similar to '{track.title}'. Return ONLY track/artist names, no explanations.",
            result_type=_LLMSearchQueries,
        )
        queries = result.result.queries if result.result else []
    except Exception as e:
        return await _ym_platform_fallback(
            f"LLM sampling unavailable ({format_sampling_unavailable_note(e)}); "
            "using platform similarity instead.",
        )

    if not queries:
        return await _ym_platform_fallback(
            "LLM returned no search queries; using platform similarity instead.",
        )

    return await svc.find_similar_llm(
        track_id=track_id,
        queries=queries,
        limit=limit,
        genre_filter_list=genre_filter_list,
        genre_blacklist_list=genre_blacklist_list,
        exclude_patterns_list=exclude_patterns_list,
    )


@tool(
    title="Find Similar Tracks",
    tags={ToolCategory.CORE.value},
    annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    icons=ICON_DISCOVERY,
    meta=TOOL_META,
)
@map_domain_errors
async def find_similar_tracks(
    track_id: Annotated[int, Field(description="Local track ID")],
    strategy: Annotated[
        Literal["ym", "llm"],
        Field(
            description=(
                "ym = Yandex Music similar API. llm = query generation via MCP sampling; "
                "if sampling is unavailable, automatically uses the same platform path as ym."
            )
        ),
    ] = "ym",
    limit: Annotated[int, Field(description="Max similar tracks to return", ge=1)] = 20,
    min_duration_ms: Annotated[
        int | None, Field(description="Minimum track duration (ms)")
    ] = None,
    max_duration_ms: Annotated[
        int | None, Field(description="Maximum track duration (ms)")
    ] = None,
    genre_filter: Annotated[list[str] | None, Field(description="Genre whitelist")] = None,
    genre_blacklist: Annotated[list[str] | None, Field(description="Genre blacklist")] = None,
    exclude_patterns: Annotated[
        list[str] | None, Field(description="Title patterns to exclude")
    ] = None,
    svc: DiscoveryService = Depends(get_discovery_service),  # noqa: B008
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict[str, Any]:
    """Finds similar tracks via YM or optional LLM search with declarative filters. Use when expanding from a seed track or generating alternatives that match your rules."""
    log = ToolContext(ctx)
    genre_filter_list = ensure_list(genre_filter) or None
    genre_blacklist_list = ensure_list(genre_blacklist) or None
    exclude_patterns_list = ensure_list(exclude_patterns) or None

    if strategy == "llm" and ctx is not None:
        return await _find_similar_llm(
            track_id,
            limit,
            min_duration_ms,
            max_duration_ms,
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

    await log.info(f"Finding similar tracks for track {track_id}...")
    return await svc.find_similar_ym(
        track_id=track_id,
        limit=limit,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
        genre_filter_list=genre_filter_list,
        genre_blacklist_list=genre_blacklist_list,
        exclude_patterns_list=exclude_patterns_list,
    )


@tool(
    title="Filter by Feedback",
    tags={ToolCategory.DISCOVERY.value},
    annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    icons=ICON_DISCOVERY,
    meta=TOOL_META,
)
@map_domain_errors
async def filter_by_feedback(
    ym_track_ids: Annotated[
        str | list[str] | None, Field(description="YM track IDs to filter")
    ] = None,
    svc: DiscoveryService = Depends(get_discovery_service),  # noqa: B008
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict[str, Any]:
    """Splits YM track IDs into liked, disliked, and neutral buckets using YM feedback. Use when pruning discovery results or prioritizing tracks that match your taste."""
    log = ToolContext(ctx)
    ids_list = ensure_list(ym_track_ids)
    if not ids_list:
        raise ToolError("ym_track_ids required")

    # BUG-21 root cause: REST gateway calls mcp.call_tool() outside any MCP
    # session, so ctx.get_state / ctx.set_state / ctx.info all raise
    # RuntimeError("session is not available"). Session state caching is a
    # pure optimization — only attempt it when a real session exists.
    # ToolContext.active encapsulates that check (single source of truth).
    state_available = log.active

    liked_set: set[str] | None = None
    disliked_set: set[str] | None = None
    if state_available and ctx is not None:
        try:
            cached_liked = await ctx.get_state("ym_liked_ids")
            cached_disliked = await ctx.get_state("ym_disliked_ids")
            if cached_liked is not None and cached_disliked is not None:
                await log.info("Using cached feedback (session state)")
                liked_set = set(cached_liked)
                disliked_set = set(cached_disliked)
        except Exception as exc:
            _log.warning("ctx.get_state failed for feedback cache: %s", exc)

    if liked_set is None or disliked_set is None:
        await log.info("Fetching liked/disliked from YM API...")
        liked_set, disliked_set = await svc.get_feedback_sets()
        if state_available and ctx is not None:
            try:
                await ctx.set_state("ym_liked_ids", sorted(liked_set))
                await ctx.set_state("ym_disliked_ids", sorted(disliked_set))
            except Exception as exc:
                _log.warning("ctx.set_state failed for feedback cache: %s", exc)

    return await svc.filter_by_feedback(
        ym_track_ids=list(ids_list),
        liked_set=liked_set,
        disliked_set=disliked_set,
    )


@tool(
    title="Expand Playlist",
    tags={ToolCategory.DISCOVERY.value},
    annotations=ANNOTATIONS_WRITE_OPEN_WORLD,
    icons=ICON_DISCOVERY,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
)
@map_domain_errors
async def expand_platform_playlist(
    playlist_id: Annotated[str, Field(description="Platform playlist ID")],
    target_count: Annotated[int, Field(description="Target playlist size", ge=1)] = 100,
    genre_filter: Annotated[list[str] | None, Field(description="Genre whitelist")] = None,
    genre_blacklist: Annotated[list[str] | None, Field(description="Genre blacklist")] = None,
    exclude_patterns: Annotated[
        list[str] | None, Field(description="Title patterns to exclude")
    ] = None,
    min_duration_ms: Annotated[
        int | None, Field(description="Minimum track duration (ms)")
    ] = None,
    max_duration_ms: Annotated[
        int | None, Field(description="Maximum track duration (ms)")
    ] = None,
    use_feedback: Annotated[bool, Field(description="Apply liked/disliked feedback gate")] = True,
    dry_run: Annotated[bool, Field(description="Preview without modifying the playlist")] = False,
    svc: DiscoveryService = Depends(get_discovery_service),  # noqa: B008
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict[str, Any]:
    """Grows a platform playlist toward a target size with similar tracks and filters."""
    log = ToolContext(ctx)
    await log.info("Fetching playlist tracks...")

    return await svc.expand_platform_playlist(
        playlist_id=playlist_id,
        target_count=target_count,
        genre_filter_list=ensure_list(genre_filter) or None,
        genre_blacklist_list=ensure_list(genre_blacklist) or None,
        exclude_patterns_list=ensure_list(exclude_patterns) or None,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
        use_feedback=use_feedback,
        dry_run=dry_run,
    )
