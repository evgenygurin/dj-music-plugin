"""Sync service — bidirectional playlist sync with music platform.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.errors import NotFoundError, ValidationError
from app.db.repositories.playlist import PlaylistRepository
from app.db.repositories.set import SetRepository
from app.db.repositories.track import TrackRepository
from app.providers.protocol import MusicProvider


class SyncService:
    """Bidirectional playlist sync with music platform."""

    def __init__(
        self,
        track_repo: TrackRepository,
        playlist_repo: PlaylistRepository,
        set_repo: SetRepository,
        provider: MusicProvider,
    ) -> None:
        self._tracks = track_repo
        self._playlists = playlist_repo
        self._sets = set_repo
        self._provider = provider

    def _get_platform_playlist_id(self, platform_ids: Any) -> str:
        """Extract platform playlist ID from platform_ids dict or JSON string."""
        pids = platform_ids or {}
        if isinstance(pids, str):
            pids = json.loads(pids)
        pid = pids.get(self._provider.provider.value)
        if not pid:
            raise ValidationError(
                f"Playlist has no {self._provider.provider.value} link. Set platform_ids first."
            )
        return str(pid)

    async def sync_playlist(
        self,
        playlist_id: int,
        direction: str = "pull",
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Sync local playlist with platform. Returns diff or sync results."""
        valid_directions = ("pull", "push", "diff")
        if direction not in valid_directions:
            raise ValidationError(
                f"Invalid direction: {direction}. Valid: {', '.join(valid_directions)}"
            )

        playlist = await self._playlists.get_with_items(playlist_id)
        if not playlist:
            raise NotFoundError("Playlist", playlist_id)

        platform_playlist_id = self._get_platform_playlist_id(playlist.platform_ids)

        # Fetch platform playlist tracks
        platform_tracks = await self._provider.get_playlist_tracks(platform_playlist_id)
        platform_ids_set = {t.id for t in platform_tracks}
        platform_by_id = {t.id: t for t in platform_tracks}

        # Build local external ID set
        local_ext_ids, local_by_ext_id = await self._build_local_provider_map(playlist)

        # Compute diff
        on_platform_only = platform_ids_set - local_ext_ids
        on_local_only = local_ext_ids - platform_ids_set

        on_platform_details = [
            {
                "external_id": eid,
                "title": platform_by_id[eid].title,
                "artists": ", ".join(a.name for a in platform_by_id[eid].artists),
            }
            for eid in list(on_platform_only)[:50]
        ]
        on_local_details = [
            {"external_id": lid, "track_id": local_by_ext_id.get(lid)}
            for lid in list(on_local_only)[:50]
        ]

        if direction == "diff" or dry_run:
            return {
                "playlist_id": playlist_id,
                "playlist_name": playlist.name,
                "platform_playlist_id": platform_playlist_id,
                "direction": direction,
                "dry_run": dry_run,
                "local_count": len(local_ext_ids),
                "platform_count": len(platform_ids_set),
                "on_platform_only": on_platform_details,
                "on_local_only": on_local_details,
                "in_sync": len(platform_ids_set & local_ext_ids),
            }

        # Apply changes
        added_count = 0
        if direction == "pull" and on_platform_only:
            added_count = await self._pull_from_platform(
                playlist_id,
                playlist,
                on_platform_only,
                platform_by_id,
            )
        elif direction == "push" and on_local_only:
            added_count = await self._push_to_platform(platform_playlist_id, on_local_only)

        return {
            "playlist_id": playlist_id,
            "direction": direction,
            "synced": added_count,
            "on_platform_only": len(on_platform_only),
            "on_local_only": len(on_local_only),
        }

    async def push_set_to_ym(
        self,
        set_id: int,
        ym_playlist_name: str | None = None,
        mode: str = "auto",
    ) -> dict[str, Any]:
        """Push DJ set as platform playlist."""
        valid_modes = ("create", "update", "auto")
        if mode not in valid_modes:
            raise ValidationError(f"Invalid mode: {mode}. Valid: {', '.join(valid_modes)}")

        dj_set = await self._sets.get_by_id(set_id)
        if not dj_set:
            raise NotFoundError("Set", set_id)

        version = await self._sets.get_latest_version(set_id)
        if not version or not version.items:
            raise ValidationError(f"Set {set_id} has no versions or tracks")

        # Collect platform track IDs (plain external IDs — adapter handles enrichment)
        platform_track_ids = await self._collect_platform_track_ids(version)
        if not platform_track_ids:
            raise ValidationError("No tracks in this set have platform IDs")

        playlist_name = ym_playlist_name or dj_set.name

        if mode in ("create", "auto"):
            pl = await self._provider.create_playlist(playlist_name)
            platform_playlist_id = pl.id  # already "owner_id:kind" from adapter
        else:
            raise ValidationError(
                "mode='update' requires playlist_id — use platform_playlists(action='get') first"
            )

        added = 0
        for batch_start in range(0, len(platform_track_ids), 20):
            batch = platform_track_ids[batch_start : batch_start + 20]
            await self._provider.add_tracks_to_playlist(platform_playlist_id, batch)
            added += len(batch)

        return {
            "set_id": set_id,
            "set_name": dj_set.name,
            "platform_playlist_id": platform_playlist_id,
            "platform_playlist_name": playlist_name,
            "tracks_pushed": added,
            "total_set_tracks": len(version.items),
            "tracks_with_platform_id": len(platform_track_ids),
            "mode_used": "create",
        }

    # ── Private ──────────────────────────────────────

    async def _build_local_provider_map(
        self,
        playlist: Any,
    ) -> tuple[set[str], dict[str, int]]:
        """Build mapping of local tracks to their platform external IDs."""
        provider_key = self._provider.provider.value
        local_ext_ids: set[str] = set()
        local_by_ext_id: dict[str, int] = {}

        if playlist.items:
            track_ids = [item.track_id for item in playlist.items]
            for tid in track_ids:
                ext = await self._tracks.get_external_id(tid, provider_key)
                if ext:
                    local_ext_ids.add(ext.external_id)
                    local_by_ext_id[ext.external_id] = tid

        return local_ext_ids, local_by_ext_id

    async def _pull_from_platform(
        self,
        playlist_id: int,
        playlist: Any,
        on_platform_only: set[str],
        platform_by_id: dict[str, Any],
    ) -> int:
        """Pull tracks from platform into local playlist."""
        provider_key = self._provider.provider.value
        max_idx = max((item.sort_index for item in playlist.items), default=-1)
        added = 0
        for i, eid in enumerate(on_platform_only):
            t = platform_by_id[eid]
            track = await self._tracks.create_with_external_id(
                title=t.title,
                duration_ms=t.duration_ms,
                platform=provider_key,
                external_id=eid,
            )
            await self._playlists.add_track(playlist_id, track.id, max_idx + 1 + i)
            added += 1
        return added

    async def _push_to_platform(
        self,
        platform_playlist_id: str,
        on_local_only: set[str],
    ) -> int:
        """Push local tracks to platform playlist."""
        track_ids = list(on_local_only)
        added = 0
        for batch_start in range(0, len(track_ids), 20):
            batch = track_ids[batch_start : batch_start + 20]
            await self._provider.add_tracks_to_playlist(platform_playlist_id, batch)
            added += len(batch)
        return added

    async def _collect_platform_track_ids(self, version: Any) -> list[str]:
        """Collect platform track IDs for set version in sort order.

        Returns plain external IDs. The adapter handles any platform-specific
        format requirements (e.g. YM's trackId:albumId) internally.
        """
        provider_key = self._provider.provider.value
        items_sorted = sorted(version.items, key=lambda i: i.sort_index)
        track_ids: list[str] = []
        for item in items_sorted:
            ext = await self._tracks.get_external_id(item.track_id, provider_key)
            if ext:
                track_ids.append(ext.external_id)
        return track_ids
