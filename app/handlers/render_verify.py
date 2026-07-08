"""Handler: run DJ-adapted mix verification for a set version."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.audio.render.verify.analysis import (
    build_verify_manifest,
    measure_output,
    measure_source,
    segment_boundaries,
)
from app.audio.render.verify.checks import VerifyConfig, run_checks
from app.audio.render.verify.report import VerifyReport
from app.config import get_settings
from app.domain.render.models import BeatgridEntry
from app.domain.render.timeline import build_render_plan
from app.handlers._context_log import safe_info
from app.handlers.render_beatgrid import render_beatgrid_handler
from app.schemas.render import RenderVerifyResult
from app.shared.workspace import render_workspace


async def render_verify_handler(
    *, ctx: Any, uow: Any, version_id: int, skip_post: bool = False
) -> RenderVerifyResult:
    if ctx is not None:
        await safe_info(
            ctx, f"render_verify: version {version_id} pre{' + post' if not skip_post else ''}"
        )

    cfg = VerifyConfig()
    inputs = await uow.set_versions.get_render_inputs(version_id)
    ws = Path(render_workspace(version_id))
    grid_path = ws / "beatgrid.json"

    if not grid_path.exists():
        await render_beatgrid_handler(ctx=ctx, uow=uow, version_id=version_id, workspace=str(ws))

    raw_grid = json.loads(grid_path.read_text())
    beatgrid_entries: dict[int, BeatgridEntry] = {}
    for g in raw_grid:
        beatgrid_entries[g["track_id"]] = BeatgridEntry(
            track_id=g["track_id"],
            trim_start_s=g["trim_start_s"],
            refined_trim_s=g.get("refined_trim_s"),
            gain_db=g.get("gain_db", 0.0),
            phase_ms=g.get("phase_ms", 0.0),
        )

    rs = get_settings().render
    plan = build_render_plan(
        inputs,
        beatgrid_entries,
        target_bpm=rs.target_bpm,
        body_bars=rs.body_bars,
        transition_bars=rs.transition_bars,
        xsplit_hz=rs.xsplit_hz,
        low_swap_bars=rs.low_swap_bars,
        outro_fade_bars=rs.outro_fade_bars,
        limiter_ceiling=rs.limiter_ceiling,
    )

    manifest = build_verify_manifest(inputs, plan, beatgrid_entries)

    src_measures: dict[int, Any] = {}
    for src in manifest.sources:
        src_measures[src.track_id] = measure_source(
            src.file_path,
            bpm_hint=src.bpm,
        )

    out_measure = None
    if not skip_post:
        mix_path = str(ws / "MIX.mp3")
        bounds = segment_boundaries(
            manifest.segment_start_s,
            manifest.segment_lengths_s,
            manifest.expected_duration_s,
        )
        out_measure = measure_output(mix_path, bounds)

    results = run_checks(manifest, src_measures, out_measure, cfg, skip_post=skip_post)
    report = VerifyReport(results=tuple(results))

    result = RenderVerifyResult(
        version_id=version_id,
        passed=report.counts.get("PASS", 0),
        warned=report.counts.get("WARN", 0),
        failed=report.counts.get("FAIL", 0),
        exit_code=report.exit_code,
        checks=[
            {"name": r.name, "status": r.status.value, "message": r.message, "detail": r.detail}
            for r in report.results
        ],
    )

    if ctx is not None:
        await safe_info(ctx, f"render_verify: {result.passed}P {result.warned}W {result.failed}F")

    return result
