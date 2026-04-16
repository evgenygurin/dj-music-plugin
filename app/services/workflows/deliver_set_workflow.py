"""Workflow for set delivery orchestration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

from app.audio.level_config import AnalysisLevel
from app.config import settings
from app.core.constants import ExportFormat
from app.core.errors import ValidationError
from app.core.utils.files import is_icloud_stub
from app.services.delivery_service import DeliveryService
from app.services.tiered_pipeline import TieredPipeline
from app.services.workflows._helpers import call_async_method

_VALID_EXPORT_FORMATS = frozenset({"m3u8", "rekordbox", "json", "cheatsheet", "cheat_sheet"})

if TYPE_CHECKING:
    from app.services.workflows.sync_playlist_workflow import SyncPlaylistWorkflow


class DeliverSetWorkflow:
    """Owns delivery and export orchestration for sets."""

    def __init__(
        self,
        delivery_service: DeliveryService,
        tiered_pipeline: TieredPipeline,
        sync_workflow: SyncPlaylistWorkflow | None = None,
    ) -> None:
        self._delivery_service = delivery_service
        self._tiered_pipeline = tiered_pipeline
        self._sync_workflow = sync_workflow

    @staticmethod
    def _set_output_dir(base: Path, set_name: str) -> Path:
        return base / set_name.replace(" ", "_").lower()

    async def _copy_audio_bundle(
        self,
        export_data: Any,
        set_dir: Path,
        log: Any = None,
    ) -> int:
        import shutil

        copied = 0
        for index, export_track in enumerate(export_data.tracks):
            if not export_track.file_path:
                continue
            src = Path(export_track.file_path)
            if not src.exists():
                await call_async_method(log, "warn", f"File not found: {src.name}")
                continue
            if is_icloud_stub(src):
                await call_async_method(log, "warn", f"iCloud stub: {src.name}")
                continue
            dest = set_dir / f"{index + 1:02d}. {export_track.artist} - {export_track.title}.mp3"
            shutil.copy2(str(src), str(dest))
            copied += 1
        return copied

    async def deliver_set(
        self,
        *,
        set_id: int,
        version: str | None = None,
        output_dir: str | None = None,
        copy_files: bool = True,
        sync_to_ym: bool = False,
        formats: list[str] | None = None,
        dry_run: bool = False,
        log: Any = None,
    ) -> dict[str, Any]:
        """Deliver a set as export artifacts plus optional copied audio."""
        await call_async_method(log, "info", f"Starting delivery for set {set_id}...")

        set_data = await self._delivery_service.load_set_for_delivery(
            set_id,
            version_label=version,
        )
        dj_set = set_data["dj_set"]
        target_version = set_data["version"]
        items = set_data["items"]

        set_track_ids = [item.track_id for item in items]
        if set_track_ids:
            analysis = await self._tiered_pipeline.ensure_level(
                set_track_ids,
                AnalysisLevel.TRANSITION,
            )
            if analysis["analyzed"] > 0:
                await call_async_method(
                    log,
                    "info",
                    f"Auto-analyzed {analysis['analyzed']} tracks (L4 transition)",
                )

        await call_async_method(log, "info", f"Stage 1/4: Loaded {len(items)} tracks")
        await call_async_method(log, "progress", 1, 4)

        scored_count, conflict_count = await self._delivery_service.score_delivery_transitions(
            items
        )
        await call_async_method(
            log,
            "info",
            f"Stage 2/4: {scored_count}/{len(items) - 1} transitions scored, "
            f"{conflict_count} conflicts",
        )
        await call_async_method(log, "progress", 2, 4)

        if conflict_count > 0 and not dry_run and getattr(log, "active", False):
            try:
                result = await call_async_method(
                    log,
                    "elicit",
                    f"Found {conflict_count} hard conflict(s) (score=0.0). Continue delivery?",
                )
                if result is not None and getattr(result, "action", None) != "accept":
                    return {
                        "aborted": True,
                        "reason": "User declined due to conflicts",
                        "conflicts": conflict_count,
                    }
            except Exception:
                logger.debug("Elicitation unavailable, skipping conflict gate")

        export_data = await self._delivery_service.build_export_data(dj_set, target_version, items)
        base_dir = Path(output_dir or settings.delivery_output_dir)
        set_dir = self._set_output_dir(base_dir, dj_set.name)
        export_formats = formats or ["m3u8", "cheat_sheet"]

        if dry_run:
            return {
                "dry_run": True,
                "set_id": set_id,
                "set_name": dj_set.name,
                "version": target_version.label,
                "track_count": len(items),
                "scored_transitions": scored_count,
                "conflicts": conflict_count,
                "output_dir": str(set_dir),
                "formats": export_formats,
            }

        set_dir.mkdir(parents=True, exist_ok=True)
        generated_files = await self._delivery_service.generate_exports(
            export_data,
            set_dir,
            dj_set.name,
            export_formats,
        )
        await call_async_method(
            log, "info", f"Stage 3/4: Generated {len(generated_files)} export files"
        )
        await call_async_method(log, "progress", 3, 4)

        copied_files = (
            await self._copy_audio_bundle(export_data, set_dir, log) if copy_files else 0
        )

        platform_sync: dict[str, Any] | None = None
        if sync_to_ym:
            if self._sync_workflow is None:
                raise ValidationError("Platform sync is unavailable")
            await call_async_method(log, "info", "Syncing delivered set to platform...")
            platform_sync = await self._sync_workflow.push_set_to_platform(
                set_id=set_id, mode="auto"
            )

        await call_async_method(log, "info", "Stage 4/4: Delivery complete")
        await call_async_method(log, "progress", 4, 4)

        return {
            "set_id": set_id,
            "set_name": dj_set.name,
            "version": target_version.label,
            "track_count": len(items),
            "scored_transitions": scored_count,
            "conflicts": conflict_count,
            "output_dir": str(set_dir),
            "generated_files": generated_files,
            "copied_audio_files": copied_files,
            "synced_to_platform": platform_sync is not None,
            "platform_sync": platform_sync,
        }

    async def export_set(
        self,
        *,
        set_id: int,
        format: str = "m3u8",
        output_path: str | None = None,
        rekordbox_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Export a set in a single format."""
        if format not in _VALID_EXPORT_FORMATS:
            raise ValidationError(
                f"Unknown format: {format}. Valid: {', '.join(sorted(_VALID_EXPORT_FORMATS))}"
            )

        set_data = await self._delivery_service.load_set_for_delivery(set_id)
        dj_set = set_data["dj_set"]
        target_version = set_data["version"]
        items = set_data["items"]

        export_data = await self._delivery_service.build_export_data(dj_set, target_version, items)

        base = Path(output_path or settings.delivery_output_dir)
        if base.is_dir() or not base.suffix:
            base.mkdir(parents=True, exist_ok=True)

        safe_name = dj_set.name.replace(" ", "_").lower()
        if format == "m3u8":
            out = base / f"{safe_name}.m3u8" if base.is_dir() else base
        elif format == "rekordbox":
            out = base / f"{safe_name}.xml" if base.is_dir() else base
        elif format == "json":
            out = base / f"{safe_name}.json" if base.is_dir() else base
        else:
            out = base / f"{safe_name}_cheat.txt" if base.is_dir() else base

        normalized_format = ExportFormat.CHEAT_SHEET if format == "cheat_sheet" else format
        path = await self._delivery_service.export_single(
            export_data,
            normalized_format,
            out,
            rekordbox_options=rekordbox_options,
        )

        return {
            "set_id": set_id,
            "format": format,
            "output_path": str(path),
            "track_count": len(items),
            "version": target_version.label,
        }
