"""Delivery & export tools (2 tools, tag: delivery)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.constants import ExportFormat
from app.mcp.dependencies import get_db_session
from app.models.audio import TrackAudioFeaturesComputed
from app.models.set import DjSet, SetItem, SetVersion
from app.models.track import TrackArtist
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

# ── Helpers ──────────────────────────────────────────


async def _build_export_data(
    session: AsyncSession,
    dj_set: DjSet,
    version: SetVersion,
    items: list[SetItem],
) -> SetExportData:
    """Build SetExportData from DB models."""
    track_repo = TrackRepository(session)
    transition_repo = TransitionRepository(session)

    export_tracks: list[ExportTrack] = []
    for item in items:
        track = await track_repo.get_by_id(item.track_id)
        if not track:
            continue

        # Load features
        stmt = select(TrackAudioFeaturesComputed).where(
            TrackAudioFeaturesComputed.track_id == track.id
        )
        result = await session.execute(stmt)
        features = result.scalar_one_or_none()

        # Load artist names
        stmt_artists = select(TrackArtist).where(TrackArtist.track_id == track.id)
        result_artists = await session.execute(stmt_artists)
        artists = list(result_artists.scalars().all())
        artist_name = (
            ", ".join(a.artist.name for a in artists if hasattr(a, "artist") and a.artist)
            or "Unknown"
        )

        # Resolve Camelot key notation
        key_camelot = None
        if features and features.key_code is not None:
            from app.core.camelot import key_code_to_camelot

            key_camelot = key_code_to_camelot(features.key_code)

        # Get file path from library
        from app.models.library import DjLibraryItem

        lib_stmt = select(DjLibraryItem).where(DjLibraryItem.track_id == track.id)
        lib_result = await session.execute(lib_stmt)
        lib_item = lib_result.scalar_one_or_none()

        export_tracks.append(
            ExportTrack(
                position=item.sort_index,
                title=track.title,
                artist=artist_name,
                duration_ms=track.duration_ms or 0,
                file_path=lib_item.file_path if lib_item else "",
                bpm=features.bpm if features else None,
                key_camelot=key_camelot,
                energy_lufs=features.integrated_lufs if features else None,
                mood=features.mood if features else None,
                notes=item.notes,
            )
        )

    # Build transitions
    export_transitions: list[ExportTransition] = []
    for i in range(len(items) - 1):
        score = await transition_repo.get_score(items[i].track_id, items[i + 1].track_id)
        export_transitions.append(
            ExportTransition(
                from_position=items[i].sort_index,
                to_position=items[i + 1].sort_index,
                score=score.overall_quality if score else None,
                bpm_delta=score.bpm_distance if score and hasattr(score, "bpm_distance") else None,
                key_distance=score.key_distance
                if score and hasattr(score, "key_distance")
                else None,
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


# ── 1. deliver_set ──────────────────────────────────


@tool(
    tags={"delivery"},
    annotations={"destructiveHint": True, "readOnlyHint": False},
    timeout=300.0,
    task=True,
)
async def deliver_set(
    set_id: int,
    version: str | None = None,
    output_dir: str | None = None,
    copy_files: bool = True,
    sync_to_ym: bool = False,
    formats: list[str] | None = None,
    dry_run: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Multi-stage set delivery: score transitions, copy files, generate exports."""
    if ctx:
        await ctx.info(f"Starting delivery for set {set_id}...")

    async with get_db_session() as session:
        set_repo = SetRepository(session)

        # Stage 1: Load set
        dj_set = await set_repo.get_by_id(set_id)
        if dj_set is None:
            raise ToolError(f"Set {set_id} not found")

        target_version = await set_repo.get_latest_version(set_id)
        if target_version is None:
            raise ToolError("No version found for this set")

        stmt = (
            select(SetItem)
            .where(SetItem.version_id == target_version.id)
            .order_by(SetItem.sort_index)
        )
        result = await session.execute(stmt)
        items = list(result.scalars().all())

        if not items:
            raise ToolError("Set has no tracks")

        if ctx:
            await ctx.info(f"Stage 1/4: Loaded {len(items)} tracks")
            await ctx.report_progress(1, 4)

        # Stage 2: Score transitions
        transition_repo = TransitionRepository(session)
        scored_count = 0
        conflict_count = 0
        for i in range(len(items) - 1):
            score = await transition_repo.get_score(items[i].track_id, items[i + 1].track_id)
            if score:
                scored_count += 1
                if score.overall_quality is not None and score.overall_quality == 0.0:
                    conflict_count += 1

        if ctx:
            await ctx.info(
                f"Stage 2/4: {scored_count}/{len(items) - 1} transitions scored, "
                f"{conflict_count} conflicts"
            )
            await ctx.report_progress(2, 4)

        # Elicitation: ask user if hard conflicts found
        if conflict_count > 0 and not dry_run and ctx:
            try:
                result = await ctx.elicit(
                    f"Found {conflict_count} hard conflict(s) (score=0.0). Continue delivery?",
                    response_type=str,
                )
                if result.action != "accept":
                    return {
                        "aborted": True,
                        "reason": "User declined due to conflicts",
                        "conflicts": conflict_count,
                    }
            except Exception:
                pass  # Client doesn't support elicitation — continue

        # Build export data
        export_data = await _build_export_data(session, dj_set, target_version, items)

        # Determine output directory
        base_dir = Path(output_dir or settings.delivery_output_dir)
        set_dir = base_dir / dj_set.name.replace(" ", "_").lower()

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
                "formats": formats or ["m3u8", "cheat_sheet"],
            }

        # Stage 3: Create output dir + exports
        set_dir.mkdir(parents=True, exist_ok=True)

        export_formats = formats or ["m3u8", "cheat_sheet"]
        generated_files: list[str] = []

        for fmt in export_formats:
            if fmt == ExportFormat.M3U8 or fmt == "m3u8":
                path = write_m3u8(export_data, set_dir / f"{dj_set.name}.m3u8")
                generated_files.append(str(path))
            elif fmt == ExportFormat.REKORDBOX_XML or fmt == "rekordbox":
                path = write_rekordbox_xml(export_data, set_dir / f"{dj_set.name}.xml")
                generated_files.append(str(path))
            elif fmt == ExportFormat.JSON_GUIDE or fmt == "json":
                path = write_json_guide(export_data, set_dir / f"{dj_set.name}.json")
                generated_files.append(str(path))
            elif fmt == ExportFormat.CHEAT_SHEET or fmt == "cheatsheet" or fmt == "cheat_sheet":
                path = write_cheat_sheet(export_data, set_dir / f"{dj_set.name}_cheat.txt")
                generated_files.append(str(path))

        if ctx:
            await ctx.info(f"Stage 3/4: Generated {len(generated_files)} export files")
            await ctx.report_progress(3, 4)

        # Stage 4: Copy audio files to set directory
        copied_files = 0
        if copy_files:
            import shutil

            audio_dir = set_dir
            for i, et in enumerate(export_data.tracks):
                if not et.file_path:
                    continue
                src = Path(et.file_path)
                if not src.exists():
                    if ctx:
                        await ctx.warning(f"File not found: {src.name}")
                    continue
                # Check iCloud stub
                stat = src.stat()
                if hasattr(stat, "st_blocks") and stat.st_blocks * 512 < stat.st_size * 0.9:
                    if ctx:
                        await ctx.warning(f"iCloud stub: {src.name}")
                    continue
                dest = audio_dir / f"{i + 1:02d}. {et.artist} - {et.title}.mp3"
                shutil.copy2(str(src), str(dest))
                copied_files += 1

        if ctx:
            await ctx.info("Stage 4/4: Delivery complete")
            await ctx.report_progress(4, 4)

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
            "synced_to_ym": False,  # YM sync is future
        }


# ── 2. export_set ───────────────────────────────────


@tool(
    tags={"delivery"},
    annotations={"readOnlyHint": False},
)
async def export_set(
    set_id: int,
    format: str = "m3u8",
    output_path: str | None = None,
    rekordbox_options: dict[str, bool] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Export set to format: m3u8, rekordbox, json, cheatsheet."""
    valid_formats = {"m3u8", "rekordbox", "json", "cheatsheet", "cheat_sheet"}
    if format not in valid_formats:
        raise ToolError(f"Unknown format: {format}. Valid: {', '.join(sorted(valid_formats))}")

    async with get_db_session() as session:
        set_repo = SetRepository(session)

        dj_set = await set_repo.get_by_id(set_id)
        if dj_set is None:
            raise ToolError(f"Set {set_id} not found")

        target_version = await set_repo.get_latest_version(set_id)
        if target_version is None:
            raise ToolError("No version found for this set")

        stmt = (
            select(SetItem)
            .where(SetItem.version_id == target_version.id)
            .order_by(SetItem.sort_index)
        )
        result = await session.execute(stmt)
        items = list(result.scalars().all())

        if not items:
            raise ToolError("Set has no tracks")

        export_data = await _build_export_data(session, dj_set, target_version, items)

        # Determine output path
        base_dir = Path(output_path or settings.delivery_output_dir)
        if base_dir.is_dir() or not base_dir.suffix:
            base_dir.mkdir(parents=True, exist_ok=True)

        safe_name = dj_set.name.replace(" ", "_").lower()

        if format == "m3u8":
            out = base_dir / f"{safe_name}.m3u8" if base_dir.is_dir() else base_dir
            path = write_m3u8(export_data, out)
        elif format == "rekordbox":
            out = base_dir / f"{safe_name}.xml" if base_dir.is_dir() else base_dir
            opts = RekordboxOptions(**rekordbox_options) if rekordbox_options else None
            path = write_rekordbox_xml(export_data, out, options=opts)
        elif format == "json":
            out = base_dir / f"{safe_name}.json" if base_dir.is_dir() else base_dir
            path = write_json_guide(export_data, out)
        elif format in ("cheatsheet", "cheat_sheet"):
            out = base_dir / f"{safe_name}_cheat.txt" if base_dir.is_dir() else base_dir
            path = write_cheat_sheet(export_data, out)
        else:
            raise ToolError(f"Unsupported format: {format}")

        return {
            "set_id": set_id,
            "format": format,
            "output_path": str(path),
            "track_count": len(items),
            "version": target_version.label,
        }
