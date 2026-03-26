"""Delivery service — set delivery and export orchestration.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.camelot import key_code_to_camelot
from app.core.errors import NotFoundError, ValidationError
from app.repositories.feature import FeatureRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.services.export import (
    ExportTrack,
    ExportTransition,
    RekordboxOptions,
    SetExportData,
    write_cheat_sheet,
    write_json_guide,
    write_m3u8,
    write_rekordbox_xml,
)


class DeliveryService:
    """Set delivery and export orchestration."""

    def __init__(
        self,
        set_repo: SetRepository,
        track_repo: TrackRepository,
        feature_repo: FeatureRepository,
        transition_repo: TransitionRepository,
    ) -> None:
        self._sets = set_repo
        self._tracks = track_repo
        self._features = feature_repo
        self._transitions = transition_repo

    async def load_set_for_delivery(self, set_id: int) -> dict[str, Any]:
        """Load set, version, and items. Returns dict with loaded data."""
        dj_set = await self._sets.get_by_id(set_id)
        if dj_set is None:
            raise NotFoundError("Set", set_id)

        version = await self._sets.get_latest_version(set_id)
        if version is None:
            raise NotFoundError("SetVersion", f"set_id={set_id}")

        items = await self._sets.get_version_items(version.id)
        if not items:
            raise ValidationError("Set has no tracks")

        return {"dj_set": dj_set, "version": version, "items": items}

    async def score_delivery_transitions(
        self,
        items: list[Any],
    ) -> tuple[int, int]:
        """Score transitions for delivery. Returns (scored_count, conflict_count)."""
        scored_count = 0
        conflict_count = 0
        for i in range(len(items) - 1):
            score = await self._transitions.get_score(items[i].track_id, items[i + 1].track_id)
            if score:
                scored_count += 1
                if score.overall_quality is not None and score.overall_quality == 0.0:
                    conflict_count += 1
        return scored_count, conflict_count

    async def build_export_data(
        self,
        dj_set: Any,
        version: Any,
        items: list[Any],
    ) -> SetExportData:
        """Build SetExportData from DB models."""
        export_tracks: list[ExportTrack] = []
        for item in items:
            track = await self._tracks.get_by_id(item.track_id)
            if not track:
                continue

            features = await self._features.get_features(track.id)

            artist_name = await self._tracks.get_artist_names(track.id) or "Unknown"

            key_camelot = None
            if features and features.key_code is not None:
                key_camelot = key_code_to_camelot(features.key_code)

            file_path = await self._tracks.get_library_file_path(track.id)

            export_tracks.append(
                ExportTrack(
                    position=item.sort_index,
                    title=track.title,
                    artist=artist_name,
                    duration_ms=track.duration_ms or 0,
                    file_path=file_path or "",
                    bpm=features.bpm if features else None,
                    key_camelot=key_camelot,
                    energy_lufs=features.integrated_lufs if features else None,
                    mood=features.mood if features else None,
                    notes=item.notes,
                )
            )

        export_transitions: list[ExportTransition] = []
        for i in range(len(items) - 1):
            score = await self._transitions.get_score(items[i].track_id, items[i + 1].track_id)
            export_transitions.append(
                ExportTransition(
                    from_position=items[i].sort_index,
                    to_position=items[i + 1].sort_index,
                    score=score.overall_quality if score else None,
                    bpm_delta=(
                        score.bpm_distance if score and hasattr(score, "bpm_distance") else None
                    ),
                    key_distance=(
                        score.key_distance if score and hasattr(score, "key_distance") else None
                    ),
                    energy_delta=None,
                    transition_type=None,
                )
            )

        return SetExportData(
            name=dj_set.name,
            version_label=version.label,
            quality_score=version.quality_score,
            tracks=export_tracks,
            transitions=export_transitions,
        )

    def generate_exports(
        self,
        export_data: SetExportData,
        set_dir: Path,
        set_name: str,
        formats: list[str],
    ) -> list[str]:
        """Generate export files in given formats. Returns paths."""
        from app.core.constants import ExportFormat

        generated_files: list[str] = []

        for fmt in formats:
            if fmt == ExportFormat.M3U8 or fmt == "m3u8":
                path = write_m3u8(export_data, set_dir / f"{set_name}.m3u8")
                generated_files.append(str(path))
            elif fmt == ExportFormat.REKORDBOX_XML or fmt == "rekordbox":
                path = write_rekordbox_xml(export_data, set_dir / f"{set_name}.xml")
                generated_files.append(str(path))
            elif fmt == ExportFormat.JSON_GUIDE or fmt == "json":
                path = write_json_guide(export_data, set_dir / f"{set_name}.json")
                generated_files.append(str(path))
            elif fmt == ExportFormat.CHEAT_SHEET or fmt in ("cheatsheet", "cheat_sheet"):
                path = write_cheat_sheet(export_data, set_dir / f"{set_name}_cheat.txt")
                generated_files.append(str(path))

        return generated_files

    @staticmethod
    def copy_audio_files(export_data: SetExportData, set_dir: Path) -> int:
        """Copy audio files to set directory. Returns count of copied files."""
        import shutil

        copied = 0
        for i, et in enumerate(export_data.tracks):
            if not et.file_path:
                continue
            src = Path(et.file_path)
            if not src.exists():
                continue
            stat = src.stat()
            if hasattr(stat, "st_blocks") and stat.st_blocks * 512 < stat.st_size * 0.9:
                continue
            dest = set_dir / f"{i + 1:02d}. {et.artist} - {et.title}.mp3"
            shutil.copy2(str(src), str(dest))
            copied += 1
        return copied

    def export_single(
        self,
        export_data: SetExportData,
        fmt: str,
        output_path: Path,
        rekordbox_options: dict[str, Any] | None = None,
    ) -> Path:
        """Export set to a single format. Returns output path."""
        if fmt == "m3u8":
            return write_m3u8(export_data, output_path)
        elif fmt == "rekordbox":
            opts = RekordboxOptions(**rekordbox_options) if rekordbox_options else None
            return write_rekordbox_xml(export_data, output_path, options=opts)
        elif fmt == "json":
            return write_json_guide(export_data, output_path)
        elif fmt in ("cheatsheet", "cheat_sheet"):
            return write_cheat_sheet(export_data, output_path)
        else:
            raise ValidationError(f"Unsupported format: {fmt}")
