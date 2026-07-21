from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.audio.render.diagnostics import scan_mix
from app.audio.render.runner import run_render
from app.config import get_settings
from app.domain.performance.subgenre_presets import resolve_preset
from app.domain.render.bar_plan import BarPlanner
from app.domain.render.models import BeatgridEntry
from app.domain.render.plan_assembler import RenderPlanner
from app.handlers._context_log import safe_info
from app.handlers._stem_resolver import StemResolver
from app.handlers.render_beatgrid import render_beatgrid_handler
from app.schemas.render import RenderMixdownResult
from app.shared.errors import ValidationError
from app.shared.render_jobs import RENDER_JOBS


def _validate_out_name(out_name: str | None) -> None:
    if not out_name:
        return
    if "/" in out_name or "\\" in out_name or out_name in {".", ".."}:
        raise ValidationError(
            f"out_name must be a bare filename, got {out_name!r}",
            details={"out_name": out_name},
        )


def _load_grid(workspace: Path) -> dict[int, BeatgridEntry]:
    grid_path = workspace / "beatgrid.json"
    rows = json.loads(grid_path.read_text())
    return {
        r["track_id"]: BeatgridEntry(
            track_id=r["track_id"],
            trim_start_s=r["trim_start_s"],
            refined_trim_s=r.get("refined_trim_s"),
            gain_db=r.get("gain_db", 0.0),
            phase_ms=r.get("phase_ms", 0.0),
        )
        for r in rows
    }


async def render_mixdown_handler(
    *,
    ctx: Any,
    uow: Any,
    version_id: int,
    workspace: str,
    timestamp: str,
    out_name: str | None = None,
    transition_bars: int | None = None,
    body_bars: int | None = None,
    refresh_grid: bool = False,
    stem: bool = True,
    subgenre: str | None = None,
    filter_sweep: str | None = None,
    echo: str | None = None,
    crossfade_curve_out: str = "tri",
    crossfade_curve_in: str = "exp",
    reverb: str | None = None,
    reverb_mix: float = 0.25,
) -> RenderMixdownResult:
    _validate_out_name(out_name)
    rs = get_settings().render

    if subgenre:
        preset = resolve_preset(subgenre)
        if preset is not None:
            preset.apply(rs)
            await safe_info(ctx, f"render_mixdown: subgenre preset '{subgenre}' applied")

    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    grid_path = ws / "beatgrid.json"

    if refresh_grid or not grid_path.exists():
        await render_beatgrid_handler(
            ctx=ctx,
            uow=uow,
            version_id=version_id,
            workspace=workspace,
            refresh=refresh_grid,
        )

    inputs = await uow.set_versions.get_render_inputs(version_id)
    grid = _load_grid(ws)

    bar_planner = BarPlanner(rs)
    planned_transition, planned_body = bar_planner.compute(
        inputs,
        grid,
        transition_bars_override=transition_bars,
        body_bars_override=body_bars,
    )
    per_transition = list(planned_transition)
    per_body = list(planned_body)

    stem_resolver = StemResolver()
    stem_paths = await stem_resolver.resolve(ctx, uow, inputs) if stem else None

    render_planner = RenderPlanner(rs)
    resolved_body = body_bars or rs.body_bars
    resolved_transition = transition_bars or rs.transition_bars

    if stem_paths:
        plan = render_planner.build_stem(
            inputs,
            stem_paths,
            grid,
            body_bars=resolved_body,
            transition_bars=resolved_transition,
            per_transition_bars=per_transition,
            per_body_bars=per_body,
            filter_sweep_preset=filter_sweep,
            echo_preset=echo,
            crossfade_curve_out=crossfade_curve_out,
            crossfade_curve_in=crossfade_curve_in,
            reverb_preset=reverb,
            reverb_mix=reverb_mix,
        )
        phase = "prepared_stem_mixdown"
    else:
        plan = render_planner.build_classic(
            inputs,
            grid,
            body_bars=resolved_body,
            transition_bars=resolved_transition,
            per_transition_bars=per_transition,
            per_body_bars=per_body,
            filter_sweep_preset=filter_sweep,
            echo_preset=echo,
            crossfade_curve_out=crossfade_curve_out,
            crossfade_curve_in=crossfade_curve_in,
            reverb_preset=reverb,
            reverb_mix=reverb_mix,
        )
        phase = "mixdown"

    job_id = f"v{version_id}-{timestamp}"
    RENDER_JOBS.start(job_id=job_id, version_id=version_id, phase=phase)
    RENDER_JOBS.update(job_id, total=plan.n, message="rendering")

    out_path = str(ws / (out_name or rs.mix_filename))
    await safe_info(ctx, f"render_mixdown ({phase}): {plan.n} segments -> {out_path}")
    try:
        run_render(plan, out_path)
    except Exception as exc:
        RENDER_JOBS.update(job_id, error=str(exc), done=True)
        raise

    sr = scan_mix(out_path)
    RENDER_JOBS.update(
        job_id,
        phase="done",
        out_path=out_path,
        progress=plan.n,
        done=True,
        message="complete",
    )
    return RenderMixdownResult(
        job_id=job_id,
        version_id=version_id,
        out_path=out_path,
        duration_s=sr.duration_s,
        true_peak_db=sr.true_peak_db,
        level_jumps=len(sr.level_jumps),
        near_silent_s=len(sr.near_silent_s),
    )
