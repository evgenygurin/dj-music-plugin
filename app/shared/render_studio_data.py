"""Shared render-studio data gatherer.

Reads every render data source for one ``set_version`` (RENDER_JOBS,
workspace ``beatgrid.json`` / ``diagnostics.json``, ``timeline_windows``) —
single source of truth reused by ``app/tools/ui/render_studio.py`` (the
interactive Prefab panel) and ``app/resources/set_design_data.py`` (the
read-only design-data dump resource). Lives under ``app.shared`` (not
``app.tools`` / ``app.domain.render``) so resources can import it without
violating the ``resources -> tools`` / ``domain.render -> repositories``
import-linter contracts.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pathlib import Path
from typing import Any

from app.config import get_settings
from app.domain.render.timeline import timeline_windows
from app.repositories.unit_of_work import UnitOfWork
from app.shared.render_jobs import RENDER_JOBS
from app.shared.render_workspace import render_workspace


async def gather_render_studio(
    uow: UnitOfWork, *, version_id: int, job_id: str | None
) -> dict[str, Any]:
    """Read every render data source for one version (DRY across UI + resource)."""
    r = get_settings().render
    inputs = await uow.set_versions.get_render_inputs(version_id)
    ws = Path(render_workspace(version_id))

    beatgrid: list[dict[str, Any]] = []
    gp = ws / "beatgrid.json"
    if gp.exists():
        beatgrid = json.loads(gp.read_text())

    diagnostics: list[dict[str, Any]] = []
    dp = ws / "diagnostics.json"
    if dp.exists():
        diagnostics = json.loads(dp.read_text()).get("windows", [])

    wins = timeline_windows(
        inputs,
        target_bpm=r.target_bpm,
        body_bars=r.body_bars,
        transition_bars=r.transition_bars,
    )
    timeline = [
        {"index": i, "title": inputs[i].title, "start_s": s, "end_s": e}
        for (i, s, e) in wins.segments
    ]

    job = None
    if job_id:
        j = RENDER_JOBS.get(job_id)
        if j is not None:
            job = asdict(j)

    return {
        "version_id": version_id,
        "n_tracks": len(inputs),
        "target_bpm": r.target_bpm,
        "beatgrid": beatgrid,
        "job": job,
        "timeline": timeline,
        "diagnostics": [d for d in diagnostics if d.get("tags")],
    }
