"""Read-only render resources (workspace files + job registry + timeline).

Cheap reads only — the heavy librosa passes are tools (render_diagnose), not
resources. Imports only app.shared / app.domain / app.config (never handlers).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from fastmcp.dependencies import Depends
from fastmcp.resources import resource

from app.config import get_settings
from app.domain.render.timeline import timeline_windows
from app.repositories.unit_of_work import UnitOfWork
from app.resources._shared import ANNOTATIONS_READ_ONLY, RESOURCE_META
from app.server.di import get_uow
from app.shared.errors import NotFoundError
from app.shared.render_jobs import RENDER_JOBS


def _workspace(version_id: int) -> Path:
    s = get_settings()
    return Path(s.delivery.output_dir) / s.render.workspace_subdir / f"v{version_id}"


@resource(
    "reference://render/defaults",
    mime_type="application/json",
    tags={"namespace:reference"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def render_defaults_resource() -> str:
    """RenderSettings constants (BPM, bars, XSPLIT, limiter)."""
    r = get_settings().render
    return json.dumps(
        {
            "target_bpm": r.target_bpm,
            "transition_bars": r.transition_bars,
            "body_bars": r.body_bars,
            "xsplit_hz": r.xsplit_hz,
            "low_swap_bars": r.low_swap_bars,
            "outro_fade_bars": r.outro_fade_bars,
            "limiter_ceiling": r.limiter_ceiling,
        }
    )


@resource(
    "local://render/jobs/{job_id}/status",
    mime_type="application/json",
    tags={"namespace:library"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def render_job_status_resource(job_id: str) -> str:
    """Live render-job progress from the in-process registry."""
    job = RENDER_JOBS.get(job_id)
    if job is None:
        raise NotFoundError("render_job", job_id)
    return json.dumps(asdict(job))


@resource(
    "local://render/jobs/{job_id}/diagnostics",
    mime_type="application/json",
    tags={"namespace:library"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def render_job_diagnostics_resource(job_id: str) -> str:
    """Saved diagnostics report for a job's version workspace."""
    # job_id is v{version_id}-{ts} or v{version_id}; extract version
    vid = job_id.split("-")[0].lstrip("v")
    path = _workspace(int(vid)) / "diagnostics.json"
    if not path.exists():
        raise NotFoundError("render_diagnostics", job_id)
    return path.read_text()


@resource(
    "local://render/{version_id}/beatgrid",
    mime_type="application/json",
    tags={"namespace:library"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def render_beatgrid_resource(version_id: int) -> str:
    """Saved beatgrid.json for a version (or 404 → run render_beatgrid)."""
    path = _workspace(version_id) / "beatgrid.json"
    if not path.exists():
        raise NotFoundError("render_beatgrid", version_id)
    return path.read_text()


@resource(
    "local://render/{version_id}/timeline",
    mime_type="application/json",
    tags={"namespace:library"},
    annotations=ANNOTATIONS_READ_ONLY,
    meta=RESOURCE_META,
)
async def render_timeline_resource(
    version_id: int,
    uow: UnitOfWork = Depends(get_uow),
) -> str:
    """Segment + transition-window timeline for a version (pure math)."""
    inputs = await uow.set_versions.get_render_inputs(version_id)
    r = get_settings().render
    wins = timeline_windows(
        inputs,
        target_bpm=r.target_bpm,
        body_bars=r.body_bars,
        transition_bars=r.transition_bars,
    )
    return json.dumps(
        {
            "version_id": version_id,
            "segments": [
                {"index": i, "title": inputs[i].title, "start_s": s, "end_s": e}
                for (i, s, e) in wins.segments
            ],
            "transitions": [
                {
                    "from_index": t.from_index,
                    "to_index": t.to_index,
                    "start_s": t.start_s,
                    "end_s": t.end_s,
                }
                for t in wins.transitions
            ],
        }
    )
