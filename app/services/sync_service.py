"""Sync service — bidirectional playlist sync with Yandex Music.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.repositories.playlist import PlaylistRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.ym.client import YandexMusicClient


class SyncService:
    """Bidirectional playlist sync with YM."""

    def __init__(
        self,
        track_repo: TrackRepository,
        playlist_repo: PlaylistRepository,
        set_repo: SetRepository,
        ym: YandexMusicClient,
    ) -> None:
        self._tracks = track_repo
        self._playlists = playlist_repo
        self._sets = set_repo
        self._ym = ym

    async def sync_playlist(
        self,
        playlist_id: int,
        direction: str = "pull",
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Sync local playlist with YM. Returns diff or sync results."""
        valid_directions = ("pull", "push", "diff")
        if direction not in valid_directions:
            raise ValidationError(
                f"Invalid direction: {direction}. Valid: {', '.join(valid_directions)}"
            )

        playlist = await self._playlists.get_with_items(playlist_id)
        if not playlist:
            raise NotFoundError("Playlist", playlist_id)

        ym_kind = self._extract_ym_kind(playlist.platform_ids)

        # Fetch YM playlist tracks
        ym_tracks = await self._ym.get_playlist_tracks(settings.ym_user_id, ym_kind)
        ym_ids = {t.id for t in ym_tracks}
        ym_by_id = {t.id: t for t in ym_tracks}

        # Build local YM ID set
        local_ym_ids, local_by_ym_id = await self._build_local_ym_map(playlist)

        # Compute diff
        on_ym_only = ym_ids - local_ym_ids
        on_local_only = local_ym_ids - ym_ids

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
            added_count = await self._pull_from_ym(
                playlist_id,
                playlist,
                on_ym_only,
                ym_by_id,
            )
        elif direction == "push" and on_local_only:
            added_count = await self._push_to_ym(ym_kind, on_local_only)

        return {
            "playlist_id": playlist_id,
            "direction": direction,
            "synced": added_count,
            "on_ym_only": len(on_ym_only),
            "on_local_only": len(on_local_only),
        }

    async def push_set_to_ym(
        self,
        set_id: int,
        ym_playlist_name: str | None = None,
        mode: str = "auto",
    ) -> dict[str, Any]:
        """Push DJ set as YM playlist."""
        valid_modes = ("create", "update", "auto")
        if mode not in valid_modes:
            raise ValidationError(f"Invalid mode: {mode}. Valid: {', '.join(valid_modes)}")

        dj_set = await self._sets.get_by_id(set_id)
        if not dj_set:
            raise NotFoundError("Set", set_id)

        version = await self._sets.get_latest_version(set_id)
        if not version or not version.items:
            raise ValidationError(f"Set {set_id} has no versions or tracks")

        # Collect YM IDs for set tracks (format: "trackId:albumId")
        ym_track_ids = await self._collect_ym_track_ids(version)
        if not ym_track_ids:
            raise ValidationError("No tracks in this set have YM IDs")

        playlist_name = ym_playlist_name or dj_set.name

        if mode in ("create", "auto"):
            pl = await self._ym.create_playlist(playlist_name)
            ym_kind = pl.kind
            revision = pl.revision or 1
        else:
            raise ValidationError(
                "mode='update' requires ym_playlist_kind — use ym_playlists(action='get') first"
            )

        added = 0
        for batch_start in range(0, len(ym_track_ids), 20):
            batch = ym_track_ids[batch_start : batch_start + 20]
            result_data = await self._ym.add_tracks_to_playlist(ym_kind, batch, revision)
            revision = result_data.get("revision", revision + 1)
            added += len(batch)

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

    # ── Private ──────────────────────────────────────

    @staticmethod
    def _extract_ym_kind(platform_ids: Any) -> int:
        """Extract YM playlist kind from platform_ids."""
        pids = platform_ids or {}
        if isinstance(pids, str):
            pids = json.loads(pids)
        ym_kind_str = pids.get("yandex_music") or pids.get("ym")
        if not ym_kind_str:
            raise ValidationError(
                "Playlist has no YM link. Set platform_ids={'yandex_music': 'kind_id'} first."
            )
        return int(str(ym_kind_str).split(":")[-1])

    async def _build_local_ym_map(
        self,
        playlist: Any,
    ) -> tuple[set[str], dict[str, int]]:
        """Build mapping of local tracks to their YM IDs."""
        local_ym_ids: set[str] = set()
        local_by_ym_id: dict[str, int] = {}

        if playlist.items:
            track_ids = [item.track_id for item in playlist.items]
            for tid in track_ids:
                ext = await self._tracks.get_external_id(tid, "yandex_music")
                if ext:
                    local_ym_ids.add(ext.external_id)
                    local_by_ym_id[ext.external_id] = tid

        return local_ym_ids, local_by_ym_id

    async def _pull_from_ym(
        self,
        playlist_id: int,
        playlist: Any,
        on_ym_only: set[str],
        ym_by_id: dict[str, Any],
    ) -> int:
        """Pull tracks from YM into local playlist."""
        max_idx = max((item.sort_index for item in playlist.items), default=-1)
        added = 0
        for i, yid in enumerate(on_ym_only):
            t = ym_by_id[yid]
            track = await self._tracks.create_with_external_id(
                title=t.title,
                duration_ms=t.duration_ms,
                platform="yandex_music",
                external_id=yid,
            )
            await self._playlists.add_track(playlist_id, track.id, max_idx + 1 + i)
            added += 1
        return added

    async def _push_to_ym(
        self,
        ym_kind: int,
        on_local_only: set[str],
    ) -> int:
        """Push local tracks to YM playlist."""
        pl_info = await self._ym.get_playlist(settings.ym_user_id, ym_kind)
        rev = pl_info.revision or 1
        added = 0
        ids_to_push = list(on_local_only)
        for batch_start in range(0, len(ids_to_push), 20):
            batch = ids_to_push[batch_start : batch_start + 20]
            result_data = await self._ym.add_tracks_to_playlist(ym_kind, batch, rev)
            rev = result_data.get("revision", rev + 1)
            added += len(batch)
        return added

    async def _collect_ym_track_ids(self, version: Any) -> list[str]:
        """Collect YM track IDs for set version tracks in trackId:albumId format.

        If albumId is missing from local metadata, batch-fetches from YM API
        and updates stored metadata. YM playlist add_tracks requires
        "trackId:albumId" format — omitting albumId causes a 400 error.
        """
        # Phase 1: collect external IDs and identify tracks missing album_id
        items_sorted = sorted(version.items, key=lambda i: i.sort_index)
        ext_map: dict[int, str] = {}  # track_id → ym_external_id
        album_map: dict[str, str] = {}  # ym_external_id → album_id
        missing_album_ym_ids: list[str] = []  # ym IDs needing album lookup

        for item in items_sorted:
            ext = await self._tracks.get_external_id(item.track_id, "yandex_music")
            if not ext:
                continue
            ext_map[item.track_id] = ext.external_id
            ym_meta = await self._tracks.get_ym_metadata(item.track_id)
            if ym_meta and ym_meta.album_id:
                album_map[ext.external_id] = ym_meta.album_id
            else:
                missing_album_ym_ids.append(ext.external_id)

        # Phase 2: batch-fetch missing album IDs from YM API
        if missing_album_ym_ids:
            fetched = await self._enrich_missing_album_ids(missing_album_ym_ids)
            album_map.update(fetched)

        # Phase 3: build trackId:albumId pairs in set order
        ym_track_ids: list[str] = []
        for item in items_sorted:
            ym_id = ext_map.get(item.track_id)
            if not ym_id:
                continue
            album_id = album_map.get(ym_id, "")
            track_ref = f"{ym_id}:{album_id}" if album_id else ym_id
            ym_track_ids.append(track_ref)
        return ym_track_ids

    async def _enrich_missing_album_ids(
        self,
        ym_ids: list[str],
    ) -> dict[str, str]:
        """Batch-fetch album IDs from YM API for tracks that lack them.

        Also updates stored YandexMetadata so future calls don't need re-fetch.
        Processes in batches of 100 (YM API limit).
        """
        result: dict[str, str] = {}
        batch_size = 100
        for start in range(0, len(ym_ids), batch_size):
            batch = ym_ids[start : start + batch_size]
            ym_tracks = await self._ym.get_tracks(batch)
            for yt in ym_tracks:
                albums = yt.albums or []
                if albums:
                    album_id = str(albums[0].get("id", ""))
                    if album_id:
                        result[yt.id] = album_id
                        # Update stored metadata so we don't re-fetch next time
                        await self._update_ym_album_id(yt.id, album_id)
        return result

    async def _update_ym_album_id(self, ym_track_id: str, album_id: str) -> None:
        """Update album_id in stored YandexMetadata for a given YM track ID."""
        from sqlalchemy import update

        from app.models.platform import YandexMetadata

        stmt = (
            update(YandexMetadata)
            .where(YandexMetadata.yandex_track_id == ym_track_id)
            .values(album_id=album_id)
        )
        await self._tracks.session.execute(stmt)
        await self._tracks.session.flush()
