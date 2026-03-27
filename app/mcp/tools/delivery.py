"""Delivery & export tools (2 tools, tag: delivery).

Thin wrappers calling DeliveryService via Depends().
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.config import settings
from app.core.constants import ExportFormat
from app.mcp.dependencies import get_delivery_service, get_tiered_pipeline
from app.services.delivery_service import DeliveryService
from app.services.export import (
    RekordboxOptions,
    write_cheat_sheet,
    write_json_guide,
    write_m3u8,
    write_rekordbox_xml,
)
from app.services.tiered_pipeline import TieredPipeline

# ── 1. deliver_set ──────────────────────────────────


@tool(
    tags={"delivery"},
    annotations={"readOnlyHint": False, "idempotentHint": True},
    timeout=300.0,
    task=True,
)
async def deliver_set(
    set_id: int,
    version: str | None = None,
    output_dir: str | None = None,
    copy_files: bool = True,
    sync_to_ym: bool = False,
    formats: Any = None,
    dry_run: bool = False,
    svc: DeliveryService = Depends(get_delivery_service),  # noqa: B008
    tiered: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Multi-stage set delivery: score transitions, copy files, generate exports."""
    from app.audio.level_config import AnalysisLevel
    from app.core.parsing import ensure_list

    formats = ensure_list(formats) or None
    if ctx:
        await ctx.info(f"Starting delivery for set {set_id}...")

    # Stage 1: Load set data via service
    set_data = await svc.load_set_for_delivery(set_id)
    dj_set = set_data["dj_set"]
    target_version = set_data["version"]
    items = set_data["items"]

    # Auto-analyze set tracks to L3 (scoring features)
    set_track_ids = [item.track_id for item in items]
    if set_track_ids:
        analysis = await tiered.ensure_level(set_track_ids, AnalysisLevel.SCORING)
        if ctx and analysis["analyzed"] > 0:
            await ctx.info(f"Auto-analyzed {analysis['analyzed']} tracks (L3 scoring)")

    if ctx:
        await ctx.info(f"Stage 1/4: Loaded {len(items)} tracks")
        await ctx.report_progress(1, 4)

    # Stage 2: Score transitions
    score_summary = await svc.score_delivery_transitions(items)
    scored_count = score_summary["scored"]
    conflict_count = score_summary["conflicts"]

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

    # Build export data via service
    export_data = await svc.build_export_data(dj_set, target_version, items)

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
        elif fmt == ExportFormat.CHEAT_SHEET or fmt in ("cheatsheet", "cheat_sheet"):
            path = write_cheat_sheet(export_data, set_dir / f"{dj_set.name}_cheat.txt")
            generated_files.append(str(path))

    if ctx:
        await ctx.info(f"Stage 3/4: Generated {len(generated_files)} export files")
        await ctx.report_progress(3, 4)

    # Stage 4: Copy audio files to set directory
    copied_files = 0
    if copy_files:
        import shutil

        for i, et in enumerate(export_data.tracks):
            if not et.file_path:
                continue
            src = Path(et.file_path)
            if not src.exists():
                if ctx:
                    await ctx.warning(f"File not found: {src.name}")
                continue
            from app.utils.files import is_icloud_stub

            if is_icloud_stub(src):
                if ctx:
                    await ctx.warning(f"iCloud stub: {src.name}")
                continue
            dest = set_dir / f"{i + 1:02d}. {et.artist} - {et.title}.mp3"
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
        "synced_to_ym": False,
    }


# ── 2. export_set ────────────────────────────────────


@tool(tags={"delivery"}, annotations={"readOnlyHint": False})
async def export_set(
    set_id: int,
    format: str = "m3u8",
    output_path: str | None = None,
    rekordbox_options: Any = None,
    svc: DeliveryService = Depends(get_delivery_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Export set to format: m3u8, rekordbox, json, cheatsheet."""
    from app.core.parsing import ensure_dict

    rekordbox_options = ensure_dict(rekordbox_options)
    valid_formats = {"m3u8", "rekordbox", "json", "cheatsheet", "cheat_sheet"}
    if format not in valid_formats:
        raise ToolError(f"Unknown format: {format}. Valid: {', '.join(sorted(valid_formats))}")

    # Load set data via service
    set_data = await svc.load_set_for_delivery(set_id)
    dj_set = set_data["dj_set"]
    target_version = set_data["version"]
    items = set_data["items"]

    export_data = await svc.build_export_data(dj_set, target_version, items)

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
