"""ui_render_studio — interactive Prefab control panel for the render pipeline.

Entry tool (``meta={"ui": True}``) with Analyze+QA / Render / Diagnose buttons
that ``CallTool`` into the real ``render_*`` tools; live job status + beatgrid
QA table + timeline + diagnostics slots. The ``render_studio_panel`` helper
(``visibility=["app"]``) re-reads the workspace / registry so status updates
flow through OUR CallTool round-trip, not the host task protocol.

Both the entry tool's fallback and the Prefab helper build from a single
``gather_render_studio`` gatherer that reads the same sources as the
``local://render/*`` resources (RENDER_JOBS, workspace beatgrid.json /
diagnostics.json, ``timeline_windows``) — no duplicated business logic.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.config import get_settings
from app.domain.render.timeline import timeline_windows
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow
from app.shared.render_jobs import RENDER_JOBS
from app.tools.ui._fallback import RenderStudioFallback, supports_ui

try:
    from fastmcp.apps import AppConfig, app_config_to_meta_dict
    from prefab_ui.app import PrefabApp
    from prefab_ui.components import (
        Badge,
        Button,
        Card,
        CardContent,
        CardHeader,
        CardTitle,
        Column,
        DataTable,
        DataTableColumn,
        Heading,
        Muted,
        Row,
        Slot,
    )
except ImportError as _exc:  # pragma: no cover — fastmcp[apps] extra missing
    raise ImportError(
        "ui_render_studio requires prefab-ui. Install with: uv sync --all-extras "
        "(or `pip install 'fastmcp[apps]'`)."
    ) from _exc


def _workspace(version_id: int) -> Path:
    s = get_settings()
    return Path(s.delivery.output_dir) / s.render.workspace_subdir / f"v{version_id}"


async def gather_render_studio(
    uow: UnitOfWork, *, version_id: int, job_id: str | None
) -> dict[str, Any]:
    """Read every render data source for one version (DRY across UI + fallback)."""
    r = get_settings().render
    inputs = await uow.set_versions.get_render_inputs(version_id)
    ws = _workspace(version_id)

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


def _panel_state(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "version_id": data["version_id"],
        "beatgrid": data["beatgrid"],
        "job": data["job"] or {},
        "timeline": data["timeline"],
        "diagnostics": data["diagnostics"],
    }


# ── Slot builders (shared by the panel helper and the entry tool) ─────


def _render_status_card(data: dict[str, Any]) -> None:
    job = data.get("job") or {}
    with Card():
        CardHeader(children=[CardTitle("Job status")])
        with CardContent():
            if job:
                Muted(
                    f"{job.get('phase', 'pending')} — {job.get('progress', 0)}/"
                    f"{job.get('total', 0)} — {job.get('message', '')}"
                )
                if job.get("error"):
                    Badge(label=f"error: {job['error']}", variant="destructive")
            else:
                Muted("No render started yet.")


def _render_beatgrid_table(data: dict[str, Any]) -> None:
    rows = data.get("beatgrid") or []
    if not rows:
        return
    with Card():
        CardHeader(children=[CardTitle("Beatgrid / QA")])
        with CardContent():
            DataTable(
                columns=[
                    DataTableColumn(key="track_id", header="Track"),
                    DataTableColumn(key="phase_ms", header="Phase (ms)"),
                    DataTableColumn(key="gain_db", header="Gain (dB)"),
                ],
                rows=[
                    {
                        "track_id": row["track_id"],
                        "phase_ms": row.get("phase_ms"),
                        "gain_db": row.get("gain_db"),
                    }
                    for row in rows
                ],
            )


def _render_timeline_card(data: dict[str, Any]) -> None:
    segs = data.get("timeline") or []
    if not segs:
        return
    with Card():
        CardHeader(children=[CardTitle("Timeline")])
        with CardContent():
            DataTable(
                columns=[
                    DataTableColumn(key="index", header="#"),
                    DataTableColumn(key="title", header="Track"),
                    DataTableColumn(key="start_s", header="Start (s)"),
                ],
                rows=[
                    {"index": s["index"], "title": s["title"], "start_s": round(s["start_s"], 1)}
                    for s in segs
                ],
            )


def _render_diagnostics_card(data: dict[str, Any]) -> None:
    flags = data.get("diagnostics") or []
    with Card():
        CardHeader(children=[CardTitle("Diagnostics")])
        with CardContent():
            if not flags:
                Muted("No flags (or not diagnosed yet).")
            for f in flags[:20]:
                Badge(
                    label=f"{f.get('offset_s')}s: {', '.join(f.get('tags', []))}",
                    variant="outline",
                )


@tool(
    name="render_studio_panel",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": True, "timeout_s": 30.0, **app_config_to_meta_dict(AppConfig(visibility=["app"]))},
    description="UI helper: re-render the render studio slots. Called from the UI only.",
    timeout=30.0,
)
async def render_studio_panel(
    version_id: Annotated[int, Field(ge=1)],
    job_id: Annotated[str | None, Field(description="Active render job id")] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> Any:
    data = await gather_render_studio(uow, version_id=version_id, job_id=job_id)
    with Column(gap=3) as view:
        _render_status_card(data)
        _render_beatgrid_table(data)
        _render_timeline_card(data)
        _render_diagnostics_card(data)
    return PrefabApp(view=view, state=_panel_state(data))
