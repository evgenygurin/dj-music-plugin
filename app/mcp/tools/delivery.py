"""Delivery & export tools (2 tools, tag: delivery).

Thin wrappers calling :class:`DeliveryService` via ``Depends()``.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.audio.level_config import AnalysisLevel
from app.config import settings
from app.core.constants import ExportFormat
from app.core.parsing import ensure_dict, ensure_list
from app.domain.export import (
    RekordboxOptions,
    write_cheat_sheet,
    write_json_guide,
    write_m3u8,
    write_rekordbox_xml,
)
from app.mcp.dependencies import get_delivery_service, get_tiered_pipeline
from app.mcp.tools._shared import (
    ANNOTATIONS_WRITE,
    ToolCategory,
    ToolContext,
    ToolTimeout,
    map_domain_errors,
)
from app.services.delivery_service import DeliveryService
from app.services.tiered_pipeline import TieredPipeline
from app.utils.files import is_icloud_stub

_DELIVER_SET_ANNOTATIONS: dict[str, bool] = {"readOnlyHint": False, "idempotentHint": True}

_VALID_EXPORT_FORMATS = frozenset(
    {"m3u8", "rekordbox", "json", "cheatsheet", "cheat_sheet"}
)


def _set_output_dir(base: Path, set_name: str) -> Path:
    """Derive the canonical output directory for a set's delivery bundle."""
    return base / set_name.replace(" ", "_").lower()


async def _write_exports(
    export_data: Any,
    set_dir: Path,
    set_name: str,
    formats: list[str],
) -> list[str]:
    """Materialise the requested export formats, returning the generated paths."""
    generated: list[str] = []
    for fmt in formats:
        if fmt in (ExportFormat.M3U8, "m3u8"):
            generated.append(str(write_m3u8(export_data, set_dir / f"{set_name}.m3u8")))
        elif fmt in (ExportFormat.REKORDBOX_XML, "rekordbox"):
            generated.append(str(write_rekordbox_xml(export_data, set_dir / f"{set_name}.xml")))
        elif fmt in (ExportFormat.JSON_GUIDE, "json"):
            generated.append(str(write_json_guide(export_data, set_dir / f"{set_name}.json")))
        elif fmt in (ExportFormat.CHEAT_SHEET, "cheatsheet", "cheat_sheet"):
            generated.append(
                str(write_cheat_sheet(export_data, set_dir / f"{set_name}_cheat.txt"))
            )
    return generated


async def _copy_audio_bundle(
    export_data: Any,
    set_dir: Path,
    log: ToolContext,
) -> int:
    """Copy the per-track MP3s into ``set_dir`` and return the count of successes."""
    copied = 0
    for i, et in enumerate(export_data.tracks):
        if not et.file_path:
            continue
        src = Path(et.file_path)
        if not src.exists():
            await log.warn(f"File not found: {src.name}")
            continue
        if is_icloud_stub(src):
            await log.warn(f"iCloud stub: {src.name}")
            continue
        dest = set_dir / f"{i + 1:02d}. {et.artist} - {et.title}.mp3"
        shutil.copy2(str(src), str(dest))
        copied += 1
    return copied


@tool(
    tags={ToolCategory.DELIVERY.value},
    annotations=_DELIVER_SET_ANNOTATIONS,
    timeout=ToolTimeout.BATCH,
    task=True,
)
@map_domain_errors
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
    log = ToolContext(ctx)
    formats_list = ensure_list(formats) or None
    await log.info(f"Starting delivery for set {set_id}...")

    # Stage 1: Load set data via service
    set_data = await svc.load_set_for_delivery(set_id)
    dj_set = set_data["dj_set"]
    target_version = set_data["version"]
    items = set_data["items"]

    # Auto-analyse set tracks to L4 (structure + scoring features)
    set_track_ids = [item.track_id for item in items]
    if set_track_ids:
        analysis = await tiered.ensure_level(set_track_ids, AnalysisLevel.TRANSITION)
        if analysis["analyzed"] > 0:
            await log.info(f"Auto-analyzed {analysis['analyzed']} tracks (L4 transition)")

    await log.info(f"Stage 1/4: Loaded {len(items)} tracks")
    await log.progress(1, 4)

    # Stage 2: Score transitions
    scored_count, conflict_count = await svc.score_delivery_transitions(items)
    await log.info(
        f"Stage 2/4: {scored_count}/{len(items) - 1} transitions scored, "
        f"{conflict_count} conflicts"
    )
    await log.progress(2, 4)

    # Elicitation: ask user if hard conflicts found
    if conflict_count > 0 and not dry_run and log.active:
        try:
            result = await log.elicit(
                f"Found {conflict_count} hard conflict(s) (score=0.0). Continue delivery?",
            )
            if result is not None and getattr(result, "action", None) != "accept":
                return {
                    "aborted": True,
                    "reason": "User declined due to conflicts",
                    "conflicts": conflict_count,
                }
        except Exception:
            pass

    # Build export data via service
    export_data = await svc.build_export_data(dj_set, target_version, items)
    base_dir = Path(output_dir or settings.delivery_output_dir)
    set_dir = _set_output_dir(base_dir, dj_set.name)
    export_formats = formats_list or ["m3u8", "cheat_sheet"]

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

    # Stage 3: Create output dir + exports
    set_dir.mkdir(parents=True, exist_ok=True)
    generated_files = await _write_exports(
        export_data, set_dir, dj_set.name, export_formats
    )
    await log.info(f"Stage 3/4: Generated {len(generated_files)} export files")
    await log.progress(3, 4)

    # Stage 4: Copy audio files to set directory
    copied_files = await _copy_audio_bundle(export_data, set_dir, log) if copy_files else 0

    await log.info("Stage 4/4: Delivery complete")
    await log.progress(4, 4)

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


@tool(tags={ToolCategory.DELIVERY.value}, annotations=ANNOTATIONS_WRITE)
@map_domain_errors
async def export_set(
    set_id: int,
    format: str = "m3u8",
    output_path: str | None = None,
    rekordbox_options: Any = None,
    svc: DeliveryService = Depends(get_delivery_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Export set to format: ``m3u8``, ``rekordbox``, ``json``, ``cheatsheet``."""
    rekordbox_options_dict = ensure_dict(rekordbox_options)
    if format not in _VALID_EXPORT_FORMATS:
        raise ToolError(
            f"Unknown format: {format}. Valid: {', '.join(sorted(_VALID_EXPORT_FORMATS))}"
        )

    set_data = await svc.load_set_for_delivery(set_id)
    dj_set = set_data["dj_set"]
    target_version = set_data["version"]
    items = set_data["items"]

    export_data = await svc.build_export_data(dj_set, target_version, items)

    base = Path(output_path or settings.delivery_output_dir)
    if base.is_dir() or not base.suffix:
        base.mkdir(parents=True, exist_ok=True)

    safe_name = dj_set.name.replace(" ", "_").lower()

    if format == "m3u8":
        out = base / f"{safe_name}.m3u8" if base.is_dir() else base
        path = write_m3u8(export_data, out)
    elif format == "rekordbox":
        out = base / f"{safe_name}.xml" if base.is_dir() else base
        opts = RekordboxOptions(**rekordbox_options_dict) if rekordbox_options_dict else None
        path = write_rekordbox_xml(export_data, out, options=opts)
    elif format == "json":
        out = base / f"{safe_name}.json" if base.is_dir() else base
        path = write_json_guide(export_data, out)
    else:  # format in {"cheatsheet", "cheat_sheet"}
        out = base / f"{safe_name}_cheat.txt" if base.is_dir() else base
        path = write_cheat_sheet(export_data, out)

    return {
        "set_id": set_id,
        "format": format,
        "output_path": str(path),
        "track_count": len(items),
        "version": target_version.label,
    }
