"""Handler: render the continuous beatmatched mix for a set version."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.audio.render.diagnostics import scan_mix
from app.audio.render.runner import run_render
from app.config import get_settings
from app.domain.render.models import BeatgridEntry
from app.domain.render.timeline import build_render_plan
from app.domain.transition.subgenre_rules import (
    body_bars_for_pair,
    classify_pair,
    transition_bars_for_pair,
)
from app.handlers._context_log import safe_info
from app.handlers.render_beatgrid import render_beatgrid_handler
from app.schemas.render import RenderMixdownResult
from app.shared.constants import TechnoSubgenre
from app.shared.errors import ValidationError
from app.shared.render_jobs import RENDER_JOBS


def _validate_out_name(out_name: str | None) -> None:
    """Reject path separators / traversal so ``ws / out_name`` can't escape the workspace.

    ``out_name`` reaches ``ffmpeg``'s output argv unsanitized; an absolute path or a
    ``..``-relative one lets a caller overwrite an arbitrary file the server process can
    write to (e.g. ``out_name="../../../etc/cron.d/x"``).
    """
    if not out_name:
        return
    if "/" in out_name or "\\" in out_name or out_name in {".", ".."}:
        raise ValidationError(
            f"out_name must be a bare filename, got {out_name!r}",
            details={"out_name": out_name},
        )


def _config_bar_override(
    subgenre: TechnoSubgenre | str | None, prefix: str, rs: Any
) -> int | None:
    if subgenre is None:
        return None
    if isinstance(subgenre, str):
        try:
            subgenre = TechnoSubgenre(subgenre)
        except ValueError:
            return None
    field_name = f"{prefix}_{subgenre.value}"
    return getattr(rs, field_name, None)


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
) -> RenderMixdownResult:
    _validate_out_name(out_name)
    rs = get_settings().render
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    grid_path = ws / "beatgrid.json"

    # ensure beatgrid exists (auto-run, like sequence_optimize auto-scores)
    if refresh_grid or not grid_path.exists():
        await render_beatgrid_handler(
            ctx=ctx, uow=uow, version_id=version_id, workspace=workspace, refresh=refresh_grid
        )

    inputs = await uow.set_versions.get_render_inputs(version_id)
    grid_rows = json.loads(grid_path.read_text())
    grid = {
        r["track_id"]: BeatgridEntry(
            track_id=r["track_id"],
            trim_start_s=r["trim_start_s"],
            refined_trim_s=r.get("refined_trim_s"),
            gain_db=r.get("gain_db", 0.0),
            phase_ms=r.get("phase_ms", 0.0),
        )
        for r in grid_rows
    }

    per_transition: list[int] = []
    per_body: list[int] = []
    for i in range(len(inputs)):
        if i < len(inputs) - 1:
            pair_type = classify_pair(
                getattr(inputs[i], "mood", None),
                getattr(inputs[i + 1], "mood", None),
            )
            per_transition.append(transition_bars_for_pair(pair_type))
        per_body.append(body_bars_for_pair(classify_pair(getattr(inputs[i], "mood", None), None)))
    for i in range(len(inputs)):
        mood = getattr(inputs[i], "mood", None)
        if i < len(inputs) - 1:
            tov = _config_bar_override(mood, "transition_bars", rs)
            if tov is not None:
                per_transition[i] = tov
        bov = _config_bar_override(mood, "body_bars", rs)
        if bov is not None:
            per_body[i] = bov

    plan = build_render_plan(
        inputs,
        grid,
        target_bpm=rs.target_bpm,
        body_bars=body_bars or rs.body_bars,
        transition_bars=transition_bars or rs.transition_bars,
        xsplit_hz=rs.xsplit_hz,
        low_swap_beats=rs.low_swap_beats,
        outro_fade_bars=rs.outro_fade_bars,
        limiter_ceiling=rs.limiter_ceiling,
        per_transition_bars=per_transition,
        per_body_bars=per_body,
    )

    job_id = f"v{version_id}-{timestamp}"
    RENDER_JOBS.start(job_id=job_id, version_id=version_id, phase="mixdown")
    RENDER_JOBS.update(job_id, total=plan.n, message="rendering")

    out_path = str(ws / (out_name or "MIX.mp3"))
    if ctx is not None:
        await safe_info(ctx, f"render_mixdown: {plan.n} segments -> {out_path}")
    try:
        run_render(plan, out_path)
    except Exception as exc:
        RENDER_JOBS.update(job_id, error=str(exc), done=True)
        raise

    sr = scan_mix(out_path)
    RENDER_JOBS.update(
        job_id, phase="done", out_path=out_path, progress=plan.n, done=True, message="complete"
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
