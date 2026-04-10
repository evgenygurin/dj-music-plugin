"""Workflow for playlist sync orchestration."""

from __future__ import annotations

from typing import Any

from app.services.sync_service import SyncService


class SyncPlaylistWorkflow:
    """Owns sync-related tool orchestration."""

    def __init__(self, sync_service: SyncService) -> None:
        self._sync_service = sync_service

    async def sync_playlist(
        self,
        *,
        playlist_id: int,
        direction: str = "pull",
        conflict_strategy: str = "source_wins",
        dry_run: bool = True,
    ) -> dict[str, Any]:
        del conflict_strategy
        return await self._sync_service.sync_playlist(
            playlist_id=playlist_id,
            direction=direction,
            dry_run=dry_run,
        )

    async def push_set_to_ym(
        self,
        *,
        set_id: int,
        ym_playlist_name: str | None = None,
        mode: str = "auto",
    ) -> dict[str, Any]:
        return await self._sync_service.push_set_to_ym(
            set_id=set_id,
            ym_playlist_name=ym_playlist_name,
            mode=mode,
        )
