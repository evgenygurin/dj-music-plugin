"""Handler: render the continuous beatmatched mix for a set version."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.audio.render.diagnostics import scan_mix
from app.audio.render.runner import run_render
from app.config import get_settings
from app.domain.render.models import BeatgridEntry
from app.domain.render.timeline import build_render_plan, build_stem_render_plan
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


def _clamp_body_bars_to_source_duration(
    inputs: list[Any],
    grid: dict[int, BeatgridEntry],
    per_transition: list[int],
    per_body: list[int],
    *,
    target_bpm: float,
) -> list[int]:
    """Prevent segments from outgrowing the available source audio.

    Short OST-style tracks can become too short after trim + time-stretch, which
    otherwise makes ffmpeg render long trailing silence and causes dropouts.
    """
    bar_s = 4.0 * (60.0 / target_bpm)
    clamped = list(per_body)
    for i, ti in enumerate(inputs):
        duration_ms = getattr(ti, "duration_ms", None)
        if not duration_ms:
            continue
        d_in = per_transition[i - 1] * bar_s if i > 0 else 0.0
        d_out = per_transition[i] * bar_s if i < len(inputs) - 1 else 0.0
        g = grid.get(ti.track_id)
        trim = g.effective_trim if g is not None else 0.0
        available_source_s = max(0.0, duration_ms / 1000.0 - trim - 1.0)
        ratio = ti.tempo_ratio(target_bpm)
        max_output_s = available_source_s / ratio if ratio > 0 else available_source_s
        body_budget_s = max_output_s - d_in - d_out
        if body_budget_s <= 0:
            clamped[i] = 1
            continue
        max_body_bars = max(1, int(body_budget_s // bar_s))
        clamped[i] = min(clamped[i], max_body_bars)
    return clamped


def _compute_bars(
    inputs: list[Any],
    grid: dict[int, BeatgridEntry],
    rs: Any,
    transition_bars: int | None,
    body_bars: int | None,
) -> tuple[list[int], list[int]]:
    """Resolve per-transition + per-body bar counts.

    Priority: explicit tool args → per-subgenre config override → mood-derived
    default. Explicit args pin every pair; they are never silently overridden.
    """
    per_transition: list[int] = []
    per_body: list[int] = []
    for i in range(len(inputs)):
        if i < len(inputs) - 1:
            if transition_bars is not None:
                per_transition.append(transition_bars)
            else:
                pair_type = classify_pair(
                    getattr(inputs[i], "mood", None),
                    getattr(inputs[i + 1], "mood", None),
                )
                per_transition.append(transition_bars_for_pair(pair_type))
        if body_bars is not None:
            per_body.append(body_bars)
        else:
            per_body.append(
                body_bars_for_pair(classify_pair(getattr(inputs[i], "mood", None), None))
            )
    for i in range(len(inputs)):
        mood = getattr(inputs[i], "mood", None)
        if i < len(inputs) - 1:
            tov = _config_bar_override(mood, "transition_bars", rs)
            if transition_bars is None and tov is not None:
                per_transition[i] = tov
        bov = _config_bar_override(mood, "body_bars", rs)
        if body_bars is None and bov is not None:
            per_body[i] = bov
    per_body = _clamp_body_bars_to_source_duration(
        inputs, grid, per_transition, per_body, target_bpm=rs.target_bpm
    )
    return per_transition, per_body


async def _separate_stems(
    ctx: Any, inputs: list[Any], ws: Path
) -> dict[int, dict[str, str]] | None:
    """Demucs 4-stem separation for every track (cached under ``ws/stems``).

    Returns ``None`` (→ classic fallback) if demucs is unavailable, a source
    file is missing, or separation raises — a stem render must never leave the
    caller without a mix.
    """
    try:
        from app.audio.deep.demucs_runner import run_demucs
    except ImportError as exc:  # pragma: no cover - env without [stems] extra
        await safe_info(ctx, f"stem separation unavailable ({exc}); classic render")
        return None

    result: dict[int, dict[str, str]] = {}
    await safe_info(ctx, f"stem render: separating {len(inputs)} tracks (demucs)...")
    for ti in inputs:
        input_file = Path(ti.file_path)
        if not input_file.exists():
            await safe_info(ctx, f"missing audio for track {ti.track_id}; classic fallback")
            return None
        try:
            stems = run_demucs(
                input_file, Path("/tmp/dj_stems"), cache_root=ws / "stems", flac=True
            )
        except Exception as exc:
            await safe_info(ctx, f"demucs failed ({exc}); classic fallback")
            return None
        result[ti.track_id] = {k: str(v) for k, v in stems.items()}
    await safe_info(ctx, f"stem render: {len(result)} tracks separated")
    return result


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
        from app.domain.performance.subgenre_presets import resolve_preset

        preset = resolve_preset(subgenre)
        if preset is not None:
            preset.apply(rs)
            await safe_info(ctx, f"render_mixdown: subgenre preset '{subgenre}' applied")

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

    per_transition, per_body = _compute_bars(inputs, grid, rs, transition_bars, body_bars)

    stem_paths_by_track = await _separate_stems(ctx, inputs, ws) if stem else None

    # Both plan builders share the same DSP/timeline kwargs — build them once.
    plan_kwargs: dict[str, Any] = {
        "target_bpm": rs.target_bpm,
        "body_bars": body_bars or rs.body_bars,
        "transition_bars": transition_bars or rs.transition_bars,
        "xsplit_low_hz": rs.xsplit_low_hz,
        "xsplit_high_hz": rs.xsplit_high_hz,
        "eq_phase_1_ratio": rs.eq_phase_1_ratio,
        "eq_phase_2_ratio": rs.eq_phase_2_ratio,
        "low_swap_beats": rs.low_swap_beats,
        "outro_fade_bars": rs.outro_fade_bars,
        "limiter_ceiling": rs.limiter_ceiling,
        "per_transition_bars": per_transition,
        "per_body_bars": per_body,
        "filter_sweep_name": filter_sweep,
        "echo_name": echo,
        "crossfade_curve_out": crossfade_curve_out,
        "crossfade_curve_in": crossfade_curve_in,
    }
    if reverb:
        plan_kwargs["reverb_name"] = reverb
        plan_kwargs["reverb_mix"] = reverb_mix
    if stem_paths_by_track:
        plan = build_stem_render_plan(inputs, stem_paths_by_track, grid, **plan_kwargs)
        phase = "stem_mixdown"
    else:
        plan = build_render_plan(inputs, grid, **plan_kwargs)
        phase = "mixdown"

    job_id = f"v{version_id}-{timestamp}"
    RENDER_JOBS.start(job_id=job_id, version_id=version_id, phase=phase)
    RENDER_JOBS.update(job_id, total=plan.n, message="rendering")

    out_path = str(ws / (out_name or rs.mix_filename))
    if ctx is not None:
        await safe_info(ctx, f"render_mixdown ({phase}): {plan.n} segments -> {out_path}")
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
