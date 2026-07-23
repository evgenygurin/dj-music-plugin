"""Handler: run scan + diagnose + structural flow analysis on a rendered mix."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.audio.render.diagnostics import analyze_set_flow, diagnose_mix
from app.handlers._context_log import safe_info
from app.schemas.render import RenderDiagnosticsResult


async def render_diagnose_handler(
    *,
    ctx: Any,
    job_id: str,
    mix_path: str,
    workspace: str,
    version_context: dict[str, Any] | None = None,
) -> RenderDiagnosticsResult:
    ws = Path(workspace)
    ws.mkdir(parents=True, exist_ok=True)
    if ctx is not None:
        await safe_info(ctx, f"render_diagnose: {mix_path}")
    rep = diagnose_mix(mix_path)
    windows = [
        {
            "offset_s": w.offset_s,
            "rms_db": w.rms_db,
            "low_db": w.low_db,
            "stereo_corr": getattr(w, "stereo_corr", None),
            "stereo_width": getattr(w, "stereo_width", None),
            "low_ratio": getattr(w, "low_ratio", None),
            "centroid_hz": getattr(w, "centroid_hz", None),
            "tags": list(w.tags),
        }
        for w in rep.windows
    ]
    payload: dict[str, Any] = {
        "job_id": job_id,
        "overall_rms_db": rep.overall_rms_db,
        "flagged": rep.flagged,
        "windows": windows,
    }

    flow: dict[str, Any] | None = None
    if version_context is not None:
        flow = analyze_set_flow(
            name=rep.name,
            duration_s=rep.duration_s,
            windows=rep.windows,
            segments=version_context.get("segments", []),
            features=version_context.get("features", {}),
            titles=version_context.get("titles", {}),
            target_subgenre=version_context.get("subgenre"),
        )
        payload["flow"] = flow

    (ws / "diagnostics.json").write_text(json.dumps(payload, indent=1))
    return RenderDiagnosticsResult(
        job_id=job_id,
        overall_rms_db=rep.overall_rms_db,
        flagged=rep.flagged,
        windows=windows,
        flow=flow,
    )
