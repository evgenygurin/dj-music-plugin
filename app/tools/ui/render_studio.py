"""ui_render_studio — interactive Prefab control panel for the render pipeline.

Entry tool (``meta={"ui": True}``) with Analyze+QA / Render / Diagnose buttons
that ``CallTool`` into the real ``render_*`` tools, then ``CallTool`` the
``render_studio_panel`` helper (``visibility=["app"]``, hidden from the model)
and write its result into the ``panel`` state key via ``SetState`` — the
canonical Prefab round-trip: a ``Slot("panel")`` in the entry view re-renders
only the panel fragment, without rebuilding the whole studio (heading/buttons
stay put). The slot is pre-seeded with the initial panel content on first
open, so the studio is never blank.

Both the entry tool and the panel helper build from a single
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
    from prefab_ui.actions import SetState, ShowToast
    from prefab_ui.actions.mcp import CallTool
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
    from prefab_ui.rx import RESULT
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


def _panel_fragment(data: dict[str, Any]) -> Any:
    """The panel content as one component tree (a Slot fragment, not a PrefabApp).

    Returned raw — the ``render_studio_panel`` tool's return value goes through
    FastMCP's own tool-response serializer (same as every other ``ui_*`` tool
    returning a bare ``Column``), which the Prefab client-side ``$result``
    resolves correctly for ``SetState("panel", RESULT)``.
    """
    with Column(gap=3) as panel:
        _render_status_card(data)
        _render_beatgrid_table(data)
        _render_timeline_card(data)
        _render_diagnostics_card(data)
    return panel


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
    description="UI helper: re-render the render studio panel. Called from the UI only.",
    timeout=30.0,
)
async def render_studio_panel(
    version_id: Annotated[int, Field(ge=1)],
    job_id: Annotated[str | None, Field(description="Active render job id")] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> Any:
    """Return the panel fragment for ``Slot("panel")`` (not a full PrefabApp).

    Its result is written into client state via ``SetState("panel", RESULT)``
    from the entry tool's buttons — the canonical Prefab round-trip.
    """
    data = await gather_render_studio(uow, version_id=version_id, job_id=job_id)
    return _panel_fragment(data)


@tool(
    name="ui_render_studio",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": True, "timeout_s": 30.0},
    description=(
        "Interactive render studio for a set version: Analyze+QA, Render, "
        "Diagnose buttons + live job status, beatgrid QA table, timeline "
        "and diagnostics. Fallback: JSON payload."
    ),
    timeout=30.0,
)
async def ui_render_studio(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> Any:
    data = await gather_render_studio(uow, version_id=version_id, job_id=None)

    if not supports_ui(ctx):
        return RenderStudioFallback(
            version_id=data["version_id"],
            n_tracks=data["n_tracks"],
            target_bpm=data["target_bpm"],
            beatgrid=data["beatgrid"],
            job=data["job"],
            timeline=data["timeline"],
            diagnostics=data["diagnostics"],
        )

    vid = version_id

    # Canonical Prefab round-trip: CallTool the render_studio_panel helper and
    # write its result into the "panel" state key; Slot("panel") re-renders
    # ONLY that fragment (heading/buttons are untouched, no full-app rebuild).
    _refresh_panel = CallTool(
        "render_studio_panel",
        arguments={"version_id": vid, "job_id": "{{ job_id }}"},
        on_success=SetState("panel", RESULT),
    )

    def _run_button(label: str, tool_name: str, *, captures_job_id: bool = False) -> None:
        on_success = (
            [SetState("job_id", RESULT.job_id), _refresh_panel]
            if captures_job_id
            else [_refresh_panel]
        )
        Button(
            label=label,
            on_click=[
                CallTool(
                    tool_name,
                    arguments={"version_id": vid},
                    on_success=on_success,
                    on_error=ShowToast(message="{{ $error }}", variant="error"),
                ),
            ],
        )

    with Column(gap=4) as view:
        Heading(f"Render Studio — version {vid}")
        Muted(f"{data['n_tracks']} tracks · target {data['target_bpm']} BPM")
        with Row(gap=2):
            _run_button("Analyze + QA", "render_beatgrid")
            # render_mixdown's result carries the job_id for status polling.
            _run_button("Render", "render_mixdown", captures_job_id=True)
            _run_button("Diagnose", "render_diagnose")
            Button(label="Refresh", on_click=[_refresh_panel])
        # Slot is pre-seeded with the initial panel fragment (below) so the
        # studio is populated on first open — no round-trip needed to see it.
        with Slot("panel"):
            Muted("Loading…")
    return PrefabApp(
        view=view,
        # PrefabApp.state is naively dumped by pydantic (unlike a tool's own
        # return value, which FastMCP serializes through the Prefab-aware
        # encoder) — pre-serialize the seed fragment via .to_json() so Slot
        # sees the full component tree, not just base Component fields.
        state={"version_id": vid, "job_id": "", "panel": _panel_fragment(data).to_json()},
    )
