"""ui_control_center — one interactive Prefab panel to drive the set lifecycle.

Entry tool (``meta={"ui": True}``) that shows library + current-set/version
state and, in Phase 1, the render pipeline buttons (Analyze+QA / Render /
Diagnose). It reuses the proven ``render_studio`` round-trip: buttons
``CallTool`` the real ``render_*`` tools, then ``CallTool`` the existing hidden
``render_studio_panel`` helper and ``SetState("panel", RESULT)`` so a
``Slot("panel")`` re-renders only the render status/QA/timeline/diagnostics
fragment.

Data is composed from three existing gatherers — ``library_dashboard._gather``
(stats), ``set_view._gather`` (tracks + energy arc), and
``render_studio.gather_render_studio`` (render status) — no duplicated business
logic and no new DB queries.
"""

from __future__ import annotations

from typing import Any

from app.repositories.unit_of_work import UnitOfWork
from app.shared.errors import NotFoundError
from app.tools.ui._fallback import ControlCenterFallback
from app.tools.ui.library_dashboard import _gather as _gather_library
from app.tools.ui.render_studio import gather_render_studio
from app.tools.ui.set_view import _gather as _gather_set


async def gather_control_center(
    uow: UnitOfWork, *, version_id: int, job_id: str | None = None
) -> dict[str, Any]:
    """Compose library + set/version + render state for one set version."""
    ver = await uow.set_versions.get(version_id)
    if ver is None:
        raise NotFoundError("set_version", version_id)
    set_id = getattr(ver, "set_id", None)

    lib = await _gather_library(uow)
    setd = await _gather_set(uow, set_id, version_id)
    render = await gather_render_studio(uow, version_id=version_id, job_id=job_id)

    tracks = [t.model_dump() for t in (setd.get("tracks") or [])]
    energy = [e.model_dump() for e in (setd.get("energy_arc") or [])]

    return {
        "version_id": version_id,
        "set_id": set_id,
        "set_name": setd.get("name"),
        "quality_score": setd.get("quality_score"),
        "n_tracks": len(tracks),
        "tracks": tracks,
        "energy_arc": energy,
        "total_tracks": lib["total_tracks"],
        "analyzed_tracks": lib["analyzed_tracks"],
        "coverage": lib["coverage"],
        "bpm_histogram": lib["bpm_histogram"],
        "mood_distribution": lib["mood_distribution"],
        "beatgrid": render["beatgrid"],
        "job": render["job"],
        "timeline": render["timeline"],
        "diagnostics": render["diagnostics"],
    }


def control_center_fallback(data: dict[str, Any]) -> ControlCenterFallback:
    """Pure dict -> Pydantic mapper for non-Prefab clients."""
    return ControlCenterFallback(
        version_id=data["version_id"],
        set_id=data.get("set_id"),
        set_name=data.get("set_name"),
        quality_score=data.get("quality_score"),
        n_tracks=data.get("n_tracks", 0),
        total_tracks=data.get("total_tracks", 0),
        analyzed_tracks=data.get("analyzed_tracks", 0),
        coverage=data.get("coverage", 0.0),
        bpm_histogram=data.get("bpm_histogram", {}),
        mood_distribution=data.get("mood_distribution", {}),
        tracks=data.get("tracks", []),
        energy_arc=data.get("energy_arc", []),
        beatgrid=data.get("beatgrid", []),
        job=data.get("job"),
        timeline=data.get("timeline", []),
        diagnostics=data.get("diagnostics", []),
    )
