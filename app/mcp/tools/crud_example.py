"""Example tool demonstrating FastMCP DI best practices.

This shows the correct pattern for using Depends() with repositories.
All other CRUD tools should follow this pattern.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import Depends
from fastmcp.server.context import Context

from app.core.schemas import PaginatedResponse, TrackBrief
from app.mcp.dependencies import get_track_repo
from app.repositories.track import TrackRepository
from app.server import mcp


@mcp.tool(tags={"core"}, annotations={"readOnlyHint": True})
async def list_tracks_example(
    limit: int = 20,
    cursor: str | None = None,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    # ✅ Correct: repo injected via Depends(), hidden from MCP schema
    repo: Annotated[TrackRepository, Depends(get_track_repo)] = None,  # type: ignore
    # Context is optional for logging/progress
    ctx: Context | None = None,
) -> dict[str, Any]:
    """List tracks with optional filters and cursor pagination.

    DI Pattern:
    - repo parameter uses Annotated[TrackRepository, Depends(get_track_repo)]
    - FastMCP hides this parameter from the MCP schema
    - Same session is reused if multiple repos are injected in one tool
    - Commit happens automatically in get_db_session context manager
    """
    if ctx:
        await ctx.info(f"Listing tracks (limit={limit})")

    # ✅ Just use the repo — session is already injected and managed
    if bpm_min is not None or bpm_max is not None:
        page = await repo.filter_by_features(
            bpm_min=bpm_min,
            bpm_max=bpm_max,
            limit=limit,
            cursor=cursor,
        )
    else:
        page = await repo.list_all(limit=limit, cursor=cursor)

    # ✅ No commit here — handled by get_db_session
    return PaginatedResponse[TrackBrief](
        items=[
            TrackBrief(
                id=t.id,
                title=t.title,
                artist_names=[],
                bpm=None,
                key_camelot=None,
                duration_ms=t.duration_ms,
            )
            for t in page.items
        ],
        next_cursor=page.next_cursor,
        total=page.total,
    ).model_dump()


# ❌ Wrong pattern (old style, DO NOT USE):
#
# async def list_tracks_wrong(
#     limit: int = 20,
#     ctx: Context | None = None,
# ) -> dict[str, Any]:
#     # ❌ Manual session management
#     async with await _get_session(ctx) as session:
#         repo = TrackRepository(session)
#         page = await repo.list_all(limit=limit)
#         # ❌ Manual commit
#         await session.commit()
#         return {...}
