"""Handler: validate a rendered mix's per-track grid alignment.

Two checks:
  (a) PLAN (pre-render, cheap): beatgrid ``bpm_measured`` vs stored ``bpm`` —
      the drift source class (see AGENTS.md render lesson #4).
  (b) MIX (post-render, heavy): each track body's measured BPM vs ``target_bpm``
      — proves rubberband honored ``tempo_ratio``. Phase measurement on the
      demucs mix is intentionally NOT done (stems shift transients).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.audio.render.grid_check import measure_body_bpm
from app.domain.render.beatgrid import BeatgridIO
from app.schemas.render import GridCheckResult, TrackGridCheck, TrackPlanCheck
from app.shared.errors import NotFoundError


def _plan_from_workspace(workspace: str) -> dict[str, Any] | None:
    path = Path(workspace) / "render_plan.json"
    if not path.exists():
        return None
    payload: dict[str, Any] = json.loads(path.read_text())
    return payload


async def render_validate_grid_handler(
    *,
    ctx: Any,
    uow: Any,
    version_id: int,
    workspace: str,
    mix_path: str,
) -> GridCheckResult:
    if not Path(mix_path).exists():
        raise NotFoundError("render_mix", mix_path)

    inputs = await uow.set_versions.get_render_inputs(version_id)
    titles = {ti.track_id: ti.title for ti in inputs}
    stored_bpm = {ti.track_id: ti.bpm for ti in inputs}

    plan = _plan_from_workspace(workspace)
    if plan is not None:
        segments = plan["segments"]
        target_bpm = float(plan["target_bpm"])
    else:
        from app.config import get_settings
        from app.domain.render.timeline import timeline_windows

        r = get_settings().render
        wins = timeline_windows(
            inputs,
            target_bpm=r.target_bpm,
            body_bars=r.body_bars,
            transition_bars=r.transition_bars,
        )
        segments = [
            {"track_id": inputs[idx].track_id, "start_s": s, "end_s": e}
            for (idx, s, e) in wins.segments
        ]
        target_bpm = r.target_bpm

    if ctx is not None:
        from app.handlers._context_log import safe_info

        await safe_info(ctx, f"render_validate_grid: {mix_path} @ {target_bpm} BPM")

    bodies = measure_body_bpm(mix_path, segments, target_bpm)
    tracks = [
        TrackGridCheck(
            track_id=b.track_id,
            title=titles.get(b.track_id),
            body_s=b.body_s,
            body_e=b.body_e,
            bpm_measured=b.bpm_measured,
            bpm_dev=b.bpm_dev,
            status=b.status,
        )
        for b in bodies
    ]

    plan_checks: list[TrackPlanCheck] = []
    grid_path = Path(workspace) / "beatgrid.json"
    if grid_path.exists():
        for entry in BeatgridIO.read(workspace):
            s = stored_bpm.get(entry.track_id)
            if s is None or entry.bpm_measured is None:
                continue
            dev = round(entry.bpm_measured - s, 3)
            plan_checks.append(
                TrackPlanCheck(
                    track_id=entry.track_id,
                    title=titles.get(entry.track_id),
                    stored_bpm=s,
                    bpm_measured=entry.bpm_measured,
                    bpm_dev=dev,
                    status=_dev_status(dev),
                )
            )

    ok = sum(1 for t in tracks if t.status == "ok")
    warn = sum(1 for t in tracks if t.status == "warn")
    fail = sum(1 for t in tracks if t.status == "fail")
    devs = [abs(t.bpm_dev) for t in tracks]
    max_dev = max(devs) if devs else 0.0
    mean_abs = round(sum(devs) / len(devs), 3) if devs else 0.0
    summary = _summarize(ok, warn, fail, max_dev)

    result = GridCheckResult(
        version_id=version_id,
        job_id=f"v{version_id}",
        mix_path=mix_path,
        target_bpm=target_bpm,
        tracks=tracks,
        plan_checks=plan_checks,
        max_dev_bpm=round(max_dev, 3),
        mean_abs_dev_bpm=mean_abs,
        ok_count=ok,
        warn_count=warn,
        fail_count=fail,
        summary=summary,
    )
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "grid_check.json").write_text(
        json.dumps(result.model_dump(), indent=1, ensure_ascii=False)
    )
    return result


def _dev_status(dev: float) -> str:
    from app.audio.render.grid_check import classify_dev

    return classify_dev(dev)


def _summarize(ok: int, warn: int, fail: int, max_dev: float) -> str:
    if fail:
        return (
            f"grid FAIL: {fail} track(s) >1.0 BPM off target (max {max_dev:.2f} BPM) - "
            "re-check bpm_measured vs stored BPM on the ORIGINAL audio, then refresh_grid + re-render."
        )
    if warn:
        return (
            f"grid WARN: {warn} track(s) 0.5-1.0 BPM off target (max {max_dev:.2f} BPM) - "
            "audible on long transitions; consider a re-render if DSP params change."
        )
    return f"grid OK: {ok} track(s) within 0.5 BPM of target (max {max_dev:.2f} BPM)."
