"""Sync tools — bidirectional playlist sync with Yandex Music (2 tools, tag: sync)."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.mcp.dependencies import get_db_session, get_ym_client
from app.models.playlist import Playlist, PlaylistItem
from app.models.set import DjSet, SetVersion
from app.models.track import Track, TrackExternalId
from app.ym.client import YandexMusicClient

# ── 1. sync_playlist ───────────────────────────────


@tool(
    tags={"sync"},
    annotations={"readOnlyHint": False, "openWorldHint": True},
)
async def sync_playlist(
    playlist_id: int,
    direction: str = "pull",
    conflict_strategy: str = "source_wins",
    dry_run: bool = True,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Sync local playlist with Yandex Music. direction: pull|push|diff. dry_run=True by default."""
    valid_directions = ("pull", "push", "diff")
    if direction not in valid_directions:
        raise ToolError(f"Invalid direction: {direction}. Valid: {', '.join(valid_directions)}")

    async with get_db_session() as session:
        # Load local playlist
        stmt = (
            select(Playlist)
            .where(Playlist.id == playlist_id)
            .options(selectinload(Playlist.items))
        )
        result = await session.execute(stmt)
        playlist = result.scalar_one_or_none()
        if not playlist:
            raise ToolError(f"Playlist {playlist_id} not found")

        # Find YM playlist kind from platform_ids
        platform_ids = playlist.platform_ids or {}
        if isinstance(platform_ids, str):
            import json

            platform_ids = json.loads(platform_ids)
        ym_kind_str = platform_ids.get("yandex_music") or platform_ids.get("ym")
        if not ym_kind_str:
            raise ToolError(
                "Playlist has no YM link. Set platform_ids={'yandex_music': 'kind_id'} first."
            )
        ym_kind = int(str(ym_kind_str).split(":")[-1])  # handle "user:kind" format

        if ctx:
            await ctx.info(f"Syncing '{playlist.name}' ↔ YM playlist kind={ym_kind}")

        # Fetch YM playlist tracks
        ym_tracks = await ym.get_playlist_tracks(settings.ym_user_id, ym_kind)
        ym_ids = {t.id for t in ym_tracks}
        ym_by_id = {t.id: t for t in ym_tracks}

        # Build local YM ID set
        local_ym_ids: set[str] = set()
        local_by_ym_id: dict[str, int] = {}  # ym_id -> track_id
        if playlist.items:
            track_ids = [item.track_id for item in playlist.items]
            for tid in track_ids:
                ext_stmt = select(TrackExternalId).where(
                    TrackExternalId.track_id == tid,
                    TrackExternalId.platform == "yandex_music",
                )
                ext_result = await session.execute(ext_stmt)
                ext = ext_result.scalar_one_or_none()
                if ext:
                    local_ym_ids.add(ext.external_id)
                    local_by_ym_id[ext.external_id] = tid

        # Compute diff
        on_ym_only = ym_ids - local_ym_ids  # tracks in YM but not local
        on_local_only = local_ym_ids - ym_ids  # tracks local but not in YM

        on_ym_details = [
            {
                "ym_id": yid,
                "title": ym_by_id[yid].title,
                "artists": ", ".join(a.get("name", "?") for a in (ym_by_id[yid].artists or [])),
            }
            for yid in list(on_ym_only)[:50]
        ]
        on_local_details = [
            {"ym_id": lid, "track_id": local_by_ym_id.get(lid)} for lid in list(on_local_only)[:50]
        ]

        if direction == "diff" or dry_run:
            return {
                "playlist_id": playlist_id,
                "playlist_name": playlist.name,
                "ym_kind": ym_kind,
                "direction": direction,
                "dry_run": dry_run,
                "local_count": len(local_ym_ids),
                "ym_count": len(ym_ids),
                "on_ym_only": on_ym_details,
                "on_local_only": on_local_details,
                "in_sync": len(ym_ids & local_ym_ids),
            }

        # Apply changes
        added_count = 0
        if direction == "pull" and on_ym_only:
            # Add YM-only tracks to local DB + playlist
            max_idx = max((item.sort_index for item in playlist.items), default=-1)
            for i, yid in enumerate(on_ym_only):
                t = ym_by_id[yid]
                track = Track(title=t.title, status=0, duration_ms=t.duration_ms)
                session.add(track)
                await session.flush()
                session.add(
                    TrackExternalId(track_id=track.id, platform="yandex_music", external_id=yid)
                )
                session.add(
                    PlaylistItem(
                        playlist_id=playlist_id, track_id=track.id, sort_index=max_idx + 1 + i
                    )
                )
                added_count += 1

        if direction == "push" and on_local_only:
            # Add local-only tracks to YM playlist
            pl_info = await ym.get_playlist(settings.ym_user_id, ym_kind)
            rev = pl_info.revision or 1
            ids_to_push = list(on_local_only)
            for batch_start in range(0, len(ids_to_push), 20):
                batch = ids_to_push[batch_start : batch_start + 20]
                result_data = await ym.add_tracks_to_playlist(ym_kind, batch, rev)
                rev = result_data.get("revision", rev + 1)
                added_count += len(batch)

        return {
            "playlist_id": playlist_id,
            "direction": direction,
            "synced": added_count,
            "on_ym_only": len(on_ym_only),
            "on_local_only": len(on_local_only),
        }


# ── 2. push_set_to_ym ─────────────────────────────


@tool(
    tags={"sync"},
    annotations={"readOnlyHint": False, "openWorldHint": True},
)
async def push_set_to_ym(
    set_id: int,
    ym_playlist_name: str | None = None,
    mode: str = "auto",
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Push DJ set as YM playlist. mode: create|update|auto."""
    valid_modes = ("create", "update", "auto")
    if mode not in valid_modes:
        raise ToolError(f"Invalid mode: {mode}. Valid: {', '.join(valid_modes)}")

    async with get_db_session() as session:
        # Load set
        dj_set = (
            await session.execute(select(DjSet).where(DjSet.id == set_id))
        ).scalar_one_or_none()
        if not dj_set:
            raise ToolError(f"Set {set_id} not found")

        # Get latest version with items
        version = (
            await session.execute(
                select(SetVersion)
                .where(SetVersion.set_id == set_id)
                .options(selectinload(SetVersion.items))
                .order_by(SetVersion.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if not version or not version.items:
            raise ToolError(f"Set {set_id} has no versions or tracks")

        # Collect YM IDs for set tracks
        ym_track_ids: list[str] = []
        for item in sorted(version.items, key=lambda i: i.sort_index):
            ext = (
                await session.execute(
                    select(TrackExternalId).where(
                        TrackExternalId.track_id == item.track_id,
                        TrackExternalId.platform == "yandex_music",
                    )
                )
            ).scalar_one_or_none()
            if ext:
                ym_track_ids.append(ext.external_id)

        if not ym_track_ids:
            raise ToolError("No tracks in this set have YM IDs")

    playlist_name = ym_playlist_name or dj_set.name

    # Create or find playlist
    if mode in ("create", "auto"):
        if ctx:
            await ctx.info(f"Creating YM playlist '{playlist_name}'...")
        pl = await ym.create_playlist(playlist_name)
        ym_kind = pl.kind
        revision = pl.revision or 1
    else:
        raise ToolError(
            "mode='update' requires ym_playlist_kind — use ym_playlists(action='get') first"
        )

    # Add tracks
    added = 0
    for batch_start in range(0, len(ym_track_ids), 20):
        batch = ym_track_ids[batch_start : batch_start + 20]
        result_data = await ym.add_tracks_to_playlist(ym_kind, batch, revision)
        revision = result_data.get("revision", revision + 1)
        added += len(batch)
        if ctx:
            await ctx.info(f"Pushed {added}/{len(ym_track_ids)} tracks")

    return {
        "set_id": set_id,
        "set_name": dj_set.name,
        "ym_playlist_kind": ym_kind,
        "ym_playlist_name": playlist_name,
        "tracks_pushed": added,
        "total_set_tracks": len(version.items),
        "tracks_with_ym_id": len(ym_track_ids),
        "mode_used": "create",
    }
