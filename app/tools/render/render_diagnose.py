"""render_diagnose — scan + per-4s defect sweep + structural flow analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.handlers.render_diagnose import render_diagnose_handler
from app.schemas.render import RenderDiagnosticsResult
from app.server.di import get_uow
from app.shared.errors import ValidationError
from app.tools.render._shared import render_mix_path, render_workspace


@tool(
    name="render_diagnose",
    tags={"namespace:render", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
    description=(
        "Scan + per-4s librosa defect sweep of a rendered mix (level jumps, "
        "dropouts, bass-thin, entry shock, low-end collapse). Also computes "
        "structural flow analysis: per-track breakdown, Camelot wheel "
        "compatibility, BPM progression, energy arc, texture diversity, and "
        "overall quality score. Heavy — background task. Pass version_id to "
        "diagnose that version's MIX.mp3, or an explicit mix_path."
    ),
    meta={"timeout_s": 900.0},
    timeout=900.0,
    task=True,
)
async def render_diagnose(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    mix_path: Annotated[
        str | None, Field(description="Explicit mix path (default workspace MIX.mp3)")
    ] = None,
    uow: Any = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> RenderDiagnosticsResult:
    path = mix_path or render_mix_path(version_id)
    if not Path(path).exists():
        raise ValidationError(f"no rendered mix at {path} — run render_mixdown first")

    inputs = await uow.set_versions.get_render_inputs(version_id)
    track_ids = [ti.track_id for ti in inputs]
    features = await uow.track_features.get_scoring_features_batch(track_ids)
    titles = {ti.track_id: ti.title for ti in inputs}

    from app.config import get_settings
    from app.domain.render.timeline import timeline_windows

    plan_path = Path(render_workspace(version_id)) / "render_plan.json"
    if plan_path.exists():
        import json as _json

        plan = _json.loads(plan_path.read_text())
        track_segments = [
            (seg["track_id"], float(seg["start_s"]), float(seg["end_s"]))
            for seg in plan.get("segments", [])
        ]
        subgenre = plan.get("subgenre")
        phrase_align_count = int(plan.get("phrase_align_count", 0))
    else:
        r = get_settings().render
        wins = timeline_windows(
            inputs,
            target_bpm=r.target_bpm,
            body_bars=r.body_bars,
            transition_bars=r.transition_bars,
        )
        track_segments = [(inputs[idx].track_id, s, e) for (idx, s, e) in wins.segments]
        subgenre = None
        phrase_align_count = 0

    version_context = {
        "segments": track_segments,
        "features": features,
        "titles": titles,
        "subgenre": subgenre,
        "phrase_align_count": phrase_align_count,
    }

    return await render_diagnose_handler(
        ctx=ctx,
        job_id=f"v{version_id}",
        mix_path=path,
        workspace=render_workspace(version_id),
        version_context=version_context,
    )
