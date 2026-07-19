"""Handler: run scan + diagnose on a rendered mix, persist the report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.audio.render.diagnostics import diagnose_mix
from app.handlers._context_log import safe_info
from app.schemas.render import RenderDiagnosticsResult


async def render_diagnose_handler(
    *, ctx: Any, job_id: str, mix_path: str, workspace: str
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
    payload = {
        "job_id": job_id,
        "overall_rms_db": rep.overall_rms_db,
        "flagged": rep.flagged,
        "windows": windows,
    }
    (ws / "diagnostics.json").write_text(json.dumps(payload, indent=1))
    return RenderDiagnosticsResult(
        job_id=job_id, overall_rms_db=rep.overall_rms_db, flagged=rep.flagged, windows=windows
    )
