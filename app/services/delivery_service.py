"""Delivery service — set delivery and export orchestration.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.camelot.wheel import key_code_to_camelot
from app.core.errors import NotFoundError, ValidationError
from app.db.models.export import AppExport
from app.db.repositories.export import ExportRepository
from app.db.repositories.feature import FeatureRepository
from app.db.repositories.set import SetRepository
from app.db.repositories.track import TrackRepository
from app.db.repositories.transition import TransitionRepository
from app.export import (
    ExportTrack,
    ExportTransition,
    RekordboxOptions,
    SetExportData,
    write_cheat_sheet,
    write_json_guide,
    write_m3u8,
    write_rekordbox_xml,
)
from app.transition.recipe import TransitionRecipe


class DeliveryService:
    """Set delivery and export orchestration."""

    def __init__(
        self,
        set_repo: SetRepository,
        track_repo: TrackRepository,
        feature_repo: FeatureRepository,
        transition_repo: TransitionRepository,
        export_repo: ExportRepository | None = None,
    ) -> None:
        self._sets = set_repo
        self._tracks = track_repo
        self._features = feature_repo
        self._transitions = transition_repo
        self._exports = export_repo

    async def load_set_for_delivery(
        self,
        set_id: int,
        version_label: str | None = None,
    ) -> dict[str, Any]:
        """Load set, version, and items. Returns dict with loaded data."""
        dj_set = await self._sets.get_by_id(set_id)
        if dj_set is None:
            raise NotFoundError("Set", set_id)

        result = await self._sets.load_version_with_items(set_id, version_label)
        if result is None:
            if version_label:
                raise NotFoundError("SetVersion", f"set_id={set_id}, label={version_label}")
            raise NotFoundError("SetVersion", f"set_id={set_id}")
        version, items = result

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

            # Load structure sections for this track
            section_rows = await self._features.get_sections(track.id)
            section_dicts = [
                {
                    "type": s.section_type,
                    "start_ms": s.start_ms,
                    "end_ms": s.end_ms,
                    "energy": s.energy,
                }
                for s in section_rows
            ]

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
                    sections=section_dicts,
                    mood=features.mood if features else None,
                    notes=item.notes,
                    mood_confidence=getattr(features, "mood_confidence", None),
                    rms_dbfs=getattr(features, "rms_dbfs", None),
                    true_peak_db=getattr(features, "true_peak_db", None),
                    crest_factor_db=getattr(features, "crest_factor_db", None),
                    danceability=getattr(features, "danceability", None),
                    hp_ratio=getattr(features, "hp_ratio", None),
                    dominant_phrase_bars=getattr(features, "dominant_phrase_bars", None),
                    variable_tempo=getattr(features, "variable_tempo", None),
                )
            )

        export_transitions: list[ExportTransition] = []
        for i in range(len(items) - 1):
            score = await self._transitions.get_score(items[i].track_id, items[i + 1].track_id)
            recipe = None
            if score and score.transition_recipe_json:
                recipe = TransitionRecipe.from_json(score.transition_recipe_json)

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
                    transition_type=recipe.fx_type.value if recipe and recipe.fx_type else None,
                    transition_bars=recipe.bars if recipe else None,
                    djay_transition=str(recipe.fx_type) if recipe and recipe.fx_type else None,
                    recipe_steps=[step.to_dict() for step in recipe.steps] if recipe else None,
                    eq_plan=recipe.eq_plan.to_dict() if recipe else None,
                    rescue_move=recipe.rescue_move if recipe else None,
                )
            )

        return SetExportData(
            name=dj_set.name,
            version_label=version.label,
            quality_score=version.quality_score,
            tracks=export_tracks,
            transitions=export_transitions,
        )

    async def generate_exports(
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

        # Log exports to DB
        await self.log_generated_exports(generated_files)

        return generated_files

    async def log_export(
        self,
        target_app: str,
        export_format: str,
        file_path: str,
        file_size: int | None = None,
    ) -> AppExport | None:
        """Log a completed export to the app_exports table.

        Returns the created AppExport or None if export_repo is not available.
        """
        if self._exports is None:
            return None
        record = AppExport(
            target_app=target_app,
            export_format=export_format,
            file_path=file_path,
            file_size=file_size,
        )
        return await self._exports.create(record)

    async def log_generated_exports(self, generated_files: list[str]) -> int:
        """Log all generated export files to DB. Returns count logged."""
        if self._exports is None:
            return 0
        logged = 0
        for file_path_str in generated_files:
            file_path = Path(file_path_str)
            suffix = file_path.suffix.lower()
            fmt_map = {
                ".m3u8": "m3u8",
                ".xml": "rekordbox_xml",
                ".json": "json_guide",
                ".txt": "cheat_sheet",
            }
            export_format = fmt_map.get(suffix, suffix.lstrip("."))
            file_size = file_path.stat().st_size if file_path.exists() else None
            await self.log_export(
                target_app="dj_music_plugin",
                export_format=export_format,
                file_path=file_path_str,
                file_size=file_size,
            )
            logged += 1
        return logged

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

    async def export_single(
        self,
        export_data: SetExportData,
        fmt: str,
        output_path: Path,
        rekordbox_options: dict[str, Any] | None = None,
    ) -> Path:
        """Export set to a single format. Returns output path."""
        if fmt == "m3u8":
            result = write_m3u8(export_data, output_path)
        elif fmt == "rekordbox":
            opts = RekordboxOptions(**rekordbox_options) if rekordbox_options else None
            result = write_rekordbox_xml(export_data, output_path, options=opts)
        elif fmt == "json":
            result = write_json_guide(export_data, output_path)
        elif fmt in ("cheatsheet", "cheat_sheet"):
            result = write_cheat_sheet(export_data, output_path)
        else:
            raise ValidationError(f"Unsupported format: {fmt}")

        # Log export to DB
        await self.log_generated_exports([str(result)])

        return result
