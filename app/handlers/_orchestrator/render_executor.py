"""Execute render plans and update render job state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.audio.render.diagnostics import scan_mix
from app.domain.render.models import RenderMode, RenderPlan
from app.domain.render.runner import run_render
from app.handlers._context_log import safe_info
from app.schemas.render import RenderMixdownResult
from app.shared.render_jobs import RENDER_JOBS


class RenderExecutor:
    async def execute(self, ctx: Any, request: Any, plan: RenderPlan) -> RenderMixdownResult:
        out_path = str(Path(request.workspace) / request.out_filename)
        phase = "prepared_stem_mixdown" if plan.mode is RenderMode.STEM else "mixdown"
        job_id = f"v{request.version_id}-{request.timestamp}"
        RENDER_JOBS.start(job_id=job_id, version_id=request.version_id, phase=phase)
        RENDER_JOBS.update(job_id, total=plan.n, message="rendering")
        await safe_info(ctx, f"render_mixdown ({phase}): {plan.n} segments -> {out_path}")
        try:
            run_render(plan, out_path)
        except Exception as exc:
            RENDER_JOBS.update(job_id, error=str(exc), done=True)
            raise
        self._persist_plan(plan, request, Path(request.workspace))
        scan = scan_mix(out_path)
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
            version_id=request.version_id,
            out_path=out_path,
            duration_s=scan.duration_s,
            true_peak_db=scan.true_peak_db,
            level_jumps=len(scan.level_jumps),
            near_silent_s=len(scan.near_silent_s),
        )

    def _persist_plan(self, plan: RenderPlan, request: Any, workspace: Path) -> None:
        """Persist the actual render geometry so diagnose can reuse it."""
        segs = plan.stem_segments if plan.stem_segments is not None else plan.segments
        timeline = [
            {"track_id": s.track_id, "start_s": s.start_s, "end_s": s.start_s + s.length_s}
            for s in segs
        ]
        payload = {
            "target_bpm": plan.target_bpm,
            "mode": plan.mode.value,
            "subgenre": getattr(request, "subgenre", None),
            "transition_bars": getattr(request, "transition_bars", None),
            "body_bars": getattr(request, "body_bars", None),
            "segments": timeline,
            "phrase_align": plan.phrase_align_count > 0,
            "phrase_align_count": plan.phrase_align_count,
        }
        import contextlib

        with contextlib.suppress(OSError):
            (workspace / "render_plan.json").write_text(json.dumps(payload, indent=1))
