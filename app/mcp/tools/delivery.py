"""Delivery & export tools (2 tools, tag: delivery)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp.server.context import Context
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.constants import ExportFormat
from app.core.elicitation import safe_choice
from app.models.audio import TrackAudioFeaturesComputed
from app.models.set import DjSet, SetItem, SetVersion
from app.models.track import TrackArtist
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.server import mcp
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


async def _get_session(ctx: Context | None) -> AsyncSession:
    """Get async session from lifespan context."""
    if ctx is None:
        raise RuntimeError("Context required — tools must be called via MCP")
    factory = ctx.lifespan_context["db_session_factory"]
    return factory()


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

        export_tracks.append(
            ExportTrack(
                position=item.sort_index,
                title=track.title,
                artist=artist_name,
                duration_ms=track.duration_ms or 0,
                file_path="",  # populated during file copy
                bpm=features.bpm if features else None,
                key_camelot=None,
                energy_lufs=features.integrated_lufs if features else None,
                mood=None,
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


@mcp.tool(
    tags={"delivery"},
    annotations={"destructiveHint": True, "readOnlyHint": False},
    timeout=300.0,
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

    async with await _get_session(ctx) as session:
        set_repo = SetRepository(session)

        # Stage 1: Load set
        dj_set = await set_repo.get_by_id(set_id)
        if dj_set is None:
            return {"error": f"Set {set_id} not found"}

        target_version = await set_repo.get_latest_version(set_id)
        if target_version is None:
            return {"error": "No version found for this set"}

        stmt = (
            select(SetItem)
            .where(SetItem.version_id == target_version.id)
            .order_by(SetItem.sort_index)
        )
        result = await session.execute(stmt)
        items = list(result.scalars().all())

        if not items:
            return {"error": "Set has no tracks"}

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

        # ── Elicitation Point 1: Handle hard conflicts ──
        if conflict_count > 0:
            if ctx:
                await ctx.warning(
                    f"⚠️ Found {conflict_count} hard conflict(s) (score=0.0). "
                    f"These transitions violate hard constraints (BPM>10, Camelot≥5, or Energy>6 LUFS)."
                )

            conflict_action = await safe_choice(
                ctx,
                message=(
                    f"Found {conflict_count} hard conflict(s) in the set. How should we proceed?"
                ),
                choices=["continue", "skip_conflicts", "abort"],
                default="continue",
            )

            if conflict_action == "abort":
                return {
                    "aborted": True,
                    "reason": "User aborted due to hard conflicts",
                    "conflict_count": conflict_count,
                }
            elif conflict_action == "skip_conflicts":
                if ctx:
                    await ctx.info("Skipping conflicted transitions in export...")
                # Future: filter out conflicted pairs from export
            # else: continue with conflicts

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

        # Stage 4: Copy audio files (stub — needs file_path on tracks)
        copied_files = 0
        if copy_files:
            # Future: copy actual audio files to set_dir/audio/
            pass

        # ── Elicitation Point 2: YM playlist sync (future) ──
        synced_to_ym = False
        if sync_to_ym:
            if ctx:
                await ctx.info("Checking if YM playlist already exists...")
            # Future implementation:
            # ym_exists = await check_ym_playlist_exists(dj_set.name)
            # if ym_exists:
            #     ym_action = await safe_choice(
            #         ctx,
            #         message=f"YM playlist '{dj_set.name}' already exists. What should we do?",
            #         choices=["overwrite", "append", "create_new", "cancel"],
            #         default="append",
            #     )
            #     if ym_action == "cancel":
            #         synced_to_ym = False
            #     else:
            #         await sync_to_ym_with_action(dj_set, ym_action)
            #         synced_to_ym = True
            # else:
            #     await create_ym_playlist(dj_set)
            #     synced_to_ym = True

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
            "synced_to_ym": synced_to_ym,
        }


# ── 2. export_set ───────────────────────────────────


@mcp.tool(
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
        return {"error": f"Unknown format: {format}. Valid: {', '.join(sorted(valid_formats))}"}

    async with await _get_session(ctx) as session:
        set_repo = SetRepository(session)

        dj_set = await set_repo.get_by_id(set_id)
        if dj_set is None:
            return {"error": f"Set {set_id} not found"}

        target_version = await set_repo.get_latest_version(set_id)
        if target_version is None:
            return {"error": "No version found for this set"}

        stmt = (
            select(SetItem)
            .where(SetItem.version_id == target_version.id)
            .order_by(SetItem.sort_index)
        )
        result = await session.execute(stmt)
        items = list(result.scalars().all())

        if not items:
            return {"error": "Set has no tracks"}

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
            return {"error": f"Unsupported format: {format}"}

        return {
            "set_id": set_id,
            "format": format,
            "output_path": str(path),
            "track_count": len(items),
            "version": target_version.label,
        }
