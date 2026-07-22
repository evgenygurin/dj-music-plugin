"""Beatgrid cache, compute, and load helpers for render orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.audio.render.kick_phase import detect_kick_trim
from app.audio.render.phase_refine import refine_phase
from app.config import get_settings
from app.domain.render.beatgrid import BeatgridIO, BeatgridLimits, clamp_entry, entry_to_row
from app.domain.render.levels import gains_to_median
from app.domain.render.models import BeatgridEntry
from app.handlers._context_log import safe_info, safe_report_progress
from app.schemas.render import RenderBeatgridResult


class BeatgridProvider:
    async def ensure(self, ctx: Any, request: Any, uow: Any) -> None:
        workspace = Path(request.workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        grid_path = workspace / "beatgrid.json"
        if grid_path.exists() and not request.refresh_grid:
            return
        await self.compute(
            ctx,
            uow,
            request.version_id,
            request.workspace,
            refresh=request.refresh_grid,
        )

    def load(self, workspace: str) -> dict[int, BeatgridEntry]:
        try:
            return {entry.track_id: entry for entry in BeatgridIO.read(workspace)}
        except FileNotFoundError:
            return {}

    async def compute(
        self,
        ctx: Any,
        uow: Any,
        version_id: int,
        workspace: str,
        *,
        refresh: bool,
    ) -> RenderBeatgridResult:
        ws = Path(workspace)
        ws.mkdir(parents=True, exist_ok=True)
        grid_path = ws / "beatgrid.json"
        if grid_path.exists() and not refresh:
            cached: list[dict[str, Any]] = json.loads(grid_path.read_text())
            return RenderBeatgridResult(version_id=version_id, tracks=cached)

        limits = BeatgridLimits.from_settings(get_settings().render)
        inputs = await uow.set_versions.get_render_inputs(version_id)
        gains = gains_to_median({ti.track_id: ti.integrated_lufs for ti in inputs})

        if ctx is not None:
            await safe_info(ctx, f"render_beatgrid: {len(inputs)} tracks for version {version_id}")

        entries: list[BeatgridEntry] = []
        for i, ti in enumerate(inputs):
            trim = detect_kick_trim(ti.file_path, start_s=ti.mix_in_ms / 1000.0, bpm=ti.bpm)
            delta_ms, refined_s = refine_phase(ti.file_path, base_trim_s=trim, bpm=ti.bpm)
            entry = BeatgridEntry(
                track_id=ti.track_id,
                trim_start_s=trim,
                refined_trim_s=refined_s,
                gain_db=gains[ti.track_id],
                phase_ms=delta_ms,
            )
            entries.append(clamp_entry(entry, limits))
            if ctx is not None:
                await safe_report_progress(ctx, progress=i + 1, total=len(inputs))

        BeatgridIO.write(workspace, entries)
        if ctx is not None:
            await safe_info(ctx, f"render_beatgrid: wrote {grid_path}")
        return RenderBeatgridResult(
            version_id=version_id,
            tracks=[entry_to_row(entry, limits) for entry in entries],
        )
