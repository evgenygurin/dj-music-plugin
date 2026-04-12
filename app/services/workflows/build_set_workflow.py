"""Workflow for set-building orchestration."""

from __future__ import annotations

from typing import Any

from app.audio.level_config import AnalysisLevel
from app.core.errors import ValidationError
from app.db.repositories.playlist import PlaylistRepository
from app.services.set.facade import SetService
from app.services.tiered_pipeline import TieredPipeline
from app.services.workflows._helpers import call_async_method


class BuildSetWorkflow:
    """Owns set build, rebuild, and scoring orchestration."""

    def __init__(
        self,
        set_service: SetService,
        tiered_pipeline: TieredPipeline,
        playlist_repo: PlaylistRepository,
    ) -> None:
        self._set_service = set_service
        self._tiered_pipeline = tiered_pipeline
        self._playlist_repo = playlist_repo

    async def _ensure_scoring_level(self, track_ids: list[int], log: Any = None) -> None:
        if not track_ids:
            return
        analysis = await self._tiered_pipeline.ensure_level(track_ids, AnalysisLevel.SCORING)
        if analysis["analyzed"] > 0:
            await call_async_method(
                log, "info", f"Auto-analyzed {analysis['analyzed']} tracks (L3 scoring)"
            )

    async def build_set(
        self,
        *,
        playlist_id: int,
        name: str,
        template: str | None = None,
        target_duration_min: int | None = None,
        algorithm: str = "greedy",
        dry_run: bool = False,
        log: Any = None,
    ) -> dict[str, Any]:
        """Build a set from playlist tracks."""
        await call_async_method(
            log, "info", f"Building set '{name}' from playlist {playlist_id}..."
        )
        await call_async_method(log, "progress", 0, 3)

        await self._ensure_scoring_level(
            await self._playlist_repo.get_track_ids(playlist_id),
            log,
        )

        if dry_run:
            return await self._set_service.build_set_dry_run(
                playlist_id=playlist_id,
                template=template,
                algorithm=algorithm,
            )

        dj_set, version, quality, used_algorithm = await self._set_service.build_set(
            playlist_id=playlist_id,
            name=name,
            template=template,
            target_duration_min=target_duration_min,
            algorithm=algorithm,
        )
        items = await self._set_service.get_version_items(version.id)
        await call_async_method(log, "info", f"Set created: {dj_set.id}, version: {version.id}")
        await call_async_method(log, "progress", 3, 3)

        return {
            "set_id": dj_set.id,
            "version_id": version.id,
            "version_label": version.label,
            "track_count": len(items),
            "algorithm": used_algorithm,
            "quality_score": round(quality, 4) if quality else None,
            "template": template,
        }

    async def rebuild_set(
        self,
        *,
        set_id: int,
        pin_tracks: list[int] | None = None,
        exclude_tracks: list[int] | None = None,
        algorithm: str = "greedy",
        version_label: str | None = None,
        log: Any = None,
    ) -> dict[str, Any]:
        """Rebuild an existing set version."""
        await call_async_method(log, "info", f"Rebuilding set {set_id}...")
        version = await self._set_service.rebuild_set(
            set_id=set_id,
            pin_tracks=pin_tracks,
            exclude_tracks=exclude_tracks,
            version_label=version_label,
            algorithm=algorithm,
        )
        return {
            "set_id": set_id,
            "version_id": version.id,
            "version_label": version.label,
        }

    async def score_transitions(
        self,
        *,
        mode: str = "set",
        set_id: int | None = None,
        from_track_id: int | None = None,
        to_track_id: int | None = None,
        track_id: int | None = None,
        top_n: int = 10,
        log: Any = None,
    ) -> dict[str, Any]:
        """Score transitions for a pair, set, or candidate list."""
        if mode == "pair" and from_track_id and to_track_id:
            await self._ensure_scoring_level([from_track_id, to_track_id], log)
            return await self._set_service.score_pair(from_track_id, to_track_id)

        if mode == "track_candidates" and track_id:
            await self._ensure_scoring_level([track_id], log)
            return await self._set_service.get_transition_candidates(track_id, top_n=top_n)

        if mode == "set" and set_id:
            version = await self._set_service.get_latest_version(set_id)
            if version is not None:
                items = await self._set_service.get_version_items(version.id)
                await self._ensure_scoring_level([item.track_id for item in items], log)
            return await self._set_service.score_set_transitions(set_id)

        raise ValidationError("Invalid mode or missing parameters")
