"""Handler: compute the beatgrid (kick trim + phase refine + LUFS gain).

DSP functions are module-level so tests can monkeypatch them without
importing librosa/ffmpeg.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.audio.render.kick_phase import detect_kick_trim
from app.audio.render.phase_refine import refine_phase
from app.domain.render.levels import gains_to_median
from app.handlers._context_log import safe_info, safe_report_progress
from app.schemas.render import RenderBeatgridResult


async def render_beatgrid_handler(
    *, ctx: Any, uow: Any, version_id: int, workspace: str, refresh: bool = False
) -> RenderBeatgridResult:
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    grid_path = ws / "beatgrid.json"

    inputs = await uow.set_versions.get_render_inputs(version_id)
    gains = gains_to_median({ti.track_id: ti.integrated_lufs for ti in inputs})

    if grid_path.exists() and not refresh:
        cached: list[dict[str, Any]] = json.loads(grid_path.read_text())
        return RenderBeatgridResult(version_id=version_id, tracks=cached)

    if ctx is not None:
        await safe_info(ctx, f"render_beatgrid: {len(inputs)} tracks for version {version_id}")
    rows: list[dict[str, Any]] = []
    for i, ti in enumerate(inputs):
        trim = detect_kick_trim(ti.file_path, start_s=ti.mix_in_ms / 1000.0, bpm=ti.bpm)
        delta_ms, refined = refine_phase(ti.file_path, base_trim_s=trim, bpm=ti.bpm)
        gain = gains[ti.track_id]
        flags = ["fixed"] if abs(delta_ms) > 40 or abs(gain) > 1.5 else []
        rows.append(
            {
                "track_id": ti.track_id,
                "trim_start_s": trim,
                "refined_trim_s": refined,
                "gain_db": gain,
                "phase_ms": delta_ms,
                "flags": flags,
            }
        )
        if ctx is not None:
            await safe_report_progress(ctx, progress=i + 1, total=len(inputs))

    grid_path.write_text(json.dumps(rows, indent=1))
    if ctx is not None:
        await safe_info(ctx, f"render_beatgrid: wrote {grid_path}")
    return RenderBeatgridResult(version_id=version_id, tracks=rows)
