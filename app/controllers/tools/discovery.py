"""Discovery, filtering & expansion tools (3 tools, tag: discovery).

Thin wrappers calling :class:`DiscoveryService` via ``Depends()``.

Tools:
- ``find_similar_tracks`` — YM API with declarative filters (+ optional LLM mode)
- ``filter_by_feedback`` — liked/disliked gate for YM track IDs
- ``expand_playlist_ym`` — high-level orchestrator (seeds → similar → filter → add)
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import BaseModel

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
from app.core.utils.parsing import ensure_list
from app.services.discovery_service import DiscoveryService

_log = logging.getLogger(__name__)


class _LLMSearchQueries(BaseModel):
    """Structured response schema for LLM similar-track query generation."""

    queries: list[str]


async def _find_similar_llm(
    track_id: int,
    limit: int,
    genre_filter_list: list[str] | None,
    genre_blacklist_list: list[str] | None,
    exclude_patterns_list: list[str] | None,
    svc: DiscoveryService,
    ctx: Context,
) -> dict[str, Any]:
    """LLM-assisted similar-track discovery — ``ctx.sample()`` is MCP-specific."""
    track = await svc._tracks.get_by_id(track_id)
    if not track:
        raise ToolError(f"Track {track_id} not found")

    try:
        result = await ctx.sample(
            f"Generate {limit} Yandex Music search queries to find techno tracks "
            f"similar to '{track.title}'. Return ONLY track/artist names, no explanations.",
            result_type=_LLMSearchQueries,
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


@tool(
    title="Find Similar Tracks",
    tags={ToolCategory.DISCOVERY.value},
    annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    icons=ICON_DISCOVERY,
    meta=TOOL_META,
)
@map_domain_errors
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

    ``strategy``: ``ym`` (default) or ``llm``.
    ``genre_filter``: whitelist; ``genre_blacklist``: blacklist.
    ``exclude_patterns``: title keywords to skip (default: remix, edit, live ...).
    """
    log = ToolContext(ctx)
    genre_filter_list = ensure_list(genre_filter) or None
    genre_blacklist_list = ensure_list(genre_blacklist) or None
    exclude_patterns_list = ensure_list(exclude_patterns) or None

    if strategy == "llm" and ctx is not None:
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
    ym_track_ids: Any = None,
    svc: DiscoveryService = Depends(get_discovery_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Apply liked/disliked feedback gate to YM track IDs.

    Returns categorised IDs: ``passed`` (unknown), ``blocked`` (disliked),
    ``boosted`` (liked). Claude decides what to do with each category.
    """
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
    """Expand YM playlist with similar tracks, applying declarative filters.

    One-call orchestrator: fetches seeds → finds similar → filters → adds.
    Prefer ``find_similar_tracks`` + ``filter_by_feedback`` + ``ym_playlists``
    for fine-grained control.
    """
    log = ToolContext(ctx)
    await log.info("Fetching playlist tracks...")

    return await svc.expand_playlist_ym(
        ym_playlist_kind=ym_playlist_kind,
        target_count=target_count,
        genre_filter_list=ensure_list(genre_filter) or None,
        genre_blacklist_list=ensure_list(genre_blacklist) or None,
        exclude_patterns_list=ensure_list(exclude_patterns) or None,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
        use_feedback=use_feedback,
        dry_run=dry_run,
    )
