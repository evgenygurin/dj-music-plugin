"""Sync tools — bidirectional playlist sync with Yandex Music (2 tools, tag: sync)."""

from __future__ import annotations

from typing import Any

from fastmcp.server.context import Context
from pydantic import BaseModel, Field

from app.core.elicitation import safe_confirm
from app.server import mcp

# ── 1. sync_playlist ───────────────────────────────


@mcp.tool(
    tags={"sync"},
    annotations={"readOnlyHint": False, "openWorldHint": True},
)
async def sync_playlist(
    playlist_id: int,
    direction: str = "pull",
    conflict_strategy: str = "source_wins",
    dry_run: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Bidirectional sync between local playlist and Yandex Music.

    direction: pull (YM->local) | push (local->YM) | bidirectional.
    conflict_strategy: source_wins | ask | skip.
    dry_run: preview changes without applying.
    """
    valid_directions = ("pull", "push", "bidirectional")
    if direction not in valid_directions:
        return {"error": f"Invalid direction: {direction}. Valid: {', '.join(valid_directions)}"}

    valid_strategies = ("source_wins", "ask", "skip")
    if conflict_strategy not in valid_strategies:
        return {
            "error": f"Invalid conflict_strategy: {conflict_strategy}. "
            f"Valid: {', '.join(valid_strategies)}"
        }

    # Stub — real implementation needs YM client from lifespan
    # Simulate conflicts for demonstration
    conflicts: list[dict[str, Any]] = []

    # Future implementation will detect actual conflicts:
    # - Track exists locally but deleted on YM
    # - Track exists on YM but deleted locally
    # - Track metadata differs between local and YM
    #
    # Example conflicts:
    # conflicts = [
    #     {"track_id": 123, "title": "Track A", "issue": "deleted_on_ym"},
    #     {"track_id": 456, "title": "Track B", "issue": "deleted_locally"},
    # ]

    # ── Elicitation Point: Handle deletion conflicts ──
    if conflicts and conflict_strategy == "ask":
        if ctx:
            await ctx.warning(f"Found {len(conflicts)} sync conflict(s)")

        resolved_conflicts: list[dict[str, Any]] = []
        for conflict in conflicts:
            if conflict["issue"] == "deleted_on_ym":
                keep_local = await safe_confirm(
                    ctx,
                    message=(
                        f"Track '{conflict['title']}' was deleted on Yandex Music. "
                        f"Keep it in local playlist?"
                    ),
                    default=True,
                )
                if keep_local is None:
                    # User cancelled
                    return {
                        "cancelled": True,
                        "reason": "User cancelled during conflict resolution",
                    }
                conflict["resolution"] = "keep_local" if keep_local else "delete_local"
                resolved_conflicts.append(conflict)

            elif conflict["issue"] == "deleted_locally":
                restore_from_ym = await safe_confirm(
                    ctx,
                    message=(
                        f"Track '{conflict['title']}' was deleted locally but exists on YM. "
                        f"Restore it from Yandex Music?"
                    ),
                    default=False,
                )
                if restore_from_ym is None:
                    return {
                        "cancelled": True,
                        "reason": "User cancelled during conflict resolution",
                    }
                conflict["resolution"] = "restore_from_ym" if restore_from_ym else "keep_deleted"
                resolved_conflicts.append(conflict)

        conflicts = resolved_conflicts

    return {
        "playlist_id": playlist_id,
        "direction": direction,
        "conflict_strategy": conflict_strategy,
        "dry_run": dry_run,
        "added": [],
        "removed": [],
        "conflicts": conflicts,
        "note": "Stub — configure DJ_YM_TOKEN for real sync",
    }


# ── 2. push_set_to_ym ─────────────────────────────


@mcp.tool(
    tags={"sync"},
    annotations={"readOnlyHint": False, "openWorldHint": True},
)
async def push_set_to_ym(
    set_id: int,
    ym_playlist_name: str | None = None,
    mode: str = "auto",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Push a DJ set as a Yandex Music playlist.

    mode: create (always new) | update (existing) | auto (create or update).
    ym_playlist_name: name for the YM playlist (defaults to set name).
    """
    valid_modes = ("create", "update", "auto")
    if mode not in valid_modes:
        return {"error": f"Invalid mode: {mode}. Valid: {', '.join(valid_modes)}"}

    # Stub — real implementation needs YM client + set data
    return {
        "set_id": set_id,
        "ym_playlist_name": ym_playlist_name,
        "mode": mode,
        "ym_playlist_kind": None,
        "tracks_pushed": 0,
        "note": "Stub — configure DJ_YM_TOKEN for real push",
    }
