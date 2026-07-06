"""ui_control_center — one interactive Prefab panel to drive the set lifecycle.

Entry tool (``meta={"ui": True}``) that shows library + current-set/version
state plus the pipeline buttons: Analyze+QA / Render / Diagnose (Phase 1) and
Build/Reorder / Analyze→L5 / conditional Sync-diff→YM (Phase 2). Buttons
``CallTool`` the real tools (``render_*``, hidden ``act_build`` /
``act_l5_set``, ``playlist_sync``), then ``CallTool`` the dedicated hidden
``control_center_panel`` helper and ``SetState("panel", RESULT)`` so a
``Slot("panel")`` re-renders only the status/QA/timeline/diagnostics fragment
(the l5 job travels through the same RENDER_JOBS registry, so the one panel
covers render and L5 jobs alike).

Data is composed from three existing gatherers — ``library_dashboard._gather``
(stats), ``set_view._gather`` (tracks + energy arc), and
``render_studio.gather_render_studio`` (render status) — no duplicated business
logic and no new DB queries.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow
from app.shared.errors import NotFoundError
from app.tools.ui._fallback import ControlCenterFallback, supports_ui
from app.tools.ui.library_dashboard import _gather as _gather_library
from app.tools.ui.render_studio import _panel_fragment, gather_render_studio
from app.tools.ui.set_view import _gather as _gather_set

try:
    from fastmcp.apps import AppConfig, app_config_to_meta_dict
    from prefab_ui.actions import SetState, ShowToast
    from prefab_ui.actions.mcp import CallTool
    from prefab_ui.app import PrefabApp
    from prefab_ui.components import (
        Button,
        Card,
        CardContent,
        CardHeader,
        CardTitle,
        Column,
        DataTable,
        DataTableColumn,
        Heading,
        Metric,
        Muted,
        Row,
        Slot,
    )
    from prefab_ui.components.charts import ChartSeries, LineChart
    from prefab_ui.rx import RESULT
except ImportError as _exc:  # pragma: no cover — fastmcp[apps] extra missing
    raise ImportError(
        "ui_control_center requires prefab-ui. Install with: uv sync --all-extras "
        "(or `pip install 'fastmcp[apps]'`)."
    ) from _exc


async def gather_control_center(
    uow: UnitOfWork, *, version_id: int, job_id: str | None = None
) -> dict[str, Any]:
    """Compose library + set/version + render state for one set version."""
    ver = await uow.set_versions.get(version_id)
    if ver is None:
        raise NotFoundError("set_version", version_id)
    set_id = ver.set_id

    s = await uow.sets.get(set_id)
    source_playlist_id = getattr(s, "source_playlist_id", None) if s is not None else None

    lib = await _gather_library(uow)
    setd = await _gather_set(uow, set_id, version_id)
    render = await gather_render_studio(uow, version_id=version_id, job_id=job_id)

    tracks = [t.model_dump() for t in (setd.get("tracks") or [])]
    energy = [e.model_dump() for e in (setd.get("energy_arc") or [])]

    return {
        "version_id": version_id,
        "set_id": set_id,
        "source_playlist_id": source_playlist_id,
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
        source_playlist_id=data.get("source_playlist_id"),
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


def _render_library_section(data: dict[str, Any]) -> None:
    with Card():
        CardHeader(children=[CardTitle("Library")])
        with CardContent(), Row(gap=4):
            Metric(label="Tracks", value=str(data["total_tracks"]))
            Metric(label="Analyzed", value=str(data["analyzed_tracks"]))
            Metric(
                label="Coverage",
                value=f"{data['coverage'] * 100:.0f}%",
                trend_sentiment=("positive" if data["coverage"] >= 0.9 else "neutral"),
            )


def _render_set_section(data: dict[str, Any]) -> None:
    rows = data.get("tracks") or []
    energy = [
        {"position": e.get("position"), "lufs": e.get("lufs") or 0.0}
        for e in (data.get("energy_arc") or [])
    ]
    set_label = data.get("set_name") or f"set #{data.get('set_id')}"
    quality = data.get("quality_score") or 0.0
    with Card():
        CardHeader(
            children=[CardTitle(f"{set_label} · v{data['version_id']} · quality {quality:.2f}")]
        )
        with CardContent():
            if energy:
                LineChart(
                    data=energy,
                    series=[ChartSeries(data_key="lufs", label="LUFS", color="#34d399")],
                    x_axis="position",
                    show_grid=True,
                    show_legend=False,
                    height=200,
                )
            if rows:
                DataTable(
                    rows=rows,
                    columns=[
                        DataTableColumn(key="position", header="#", sortable=True, width="48px"),
                        DataTableColumn(key="title", header="Title", sortable=True),
                        DataTableColumn(key="bpm", header="BPM", sortable=True, width="72px"),
                        DataTableColumn(key="camelot", header="Key", width="60px"),
                        DataTableColumn(key="lufs", header="LUFS", sortable=True, width="72px"),
                        DataTableColumn(key="mood", header="Mood"),
                    ],
                    paginated=len(rows) > 25,
                    page_size=25,
                )
            else:
                Muted("No tracks in this version.")


@tool(
    name="control_center_panel",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={
        "ui": True,
        "timeout_s": 30.0,
        **app_config_to_meta_dict(AppConfig(visibility=["app"])),
    },
    description=("UI helper: re-render the control center status panel. Called from the UI only."),
    timeout=30.0,
)
async def control_center_panel(
    version_id: Annotated[int, Field(ge=1)],
    job_id: Annotated[str | None, Field(description="Active job id (render or l5)")] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> Any:
    """Return the panel fragment for ``Slot("panel")`` (not a full PrefabApp)."""
    data = await gather_control_center(uow, version_id=version_id, job_id=job_id)
    return _panel_fragment(data)


@tool(
    name="ui_control_center",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": True, "timeout_s": 30.0},
    description=(
        "Interactive DJ control center for a set version: library + set/version "
        "overview and render pipeline buttons (Analyze+QA, Render, Diagnose) with "
        "live status. Fallback: JSON payload."
    ),
    timeout=30.0,
)
async def ui_control_center(
    version_id: Annotated[int, Field(ge=1, description="Set version ID")],
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> Any:
    data = await gather_control_center(uow, version_id=version_id, job_id=None)

    if not supports_ui(ctx):
        return control_center_fallback(data)

    vid = version_id

    _refresh_panel = CallTool(
        "control_center_panel",
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

    with Column(gap=4, css_class="p-6") as view:
        Heading(f"DJ Control Center — version {vid}")
        _render_library_section(data)
        _render_set_section(data)
        with Row(gap=2):
            _run_button("Analyze + QA", "render_beatgrid")
            _run_button("Render", "render_mixdown", captures_job_id=True)
            _run_button("Diagnose", "render_diagnose")
            Button(
                label="Build / Reorder",
                on_click=[
                    CallTool(
                        "act_build",
                        arguments={"version_id": vid},
                        on_success=[
                            ShowToast(
                                message="New version created: {{ $result.new_version_id }}",
                                variant="success",
                            ),
                            _refresh_panel,
                        ],
                        on_error=ShowToast(message="{{ $error }}", variant="error"),
                    ),
                ],
            )
            _run_button("Analyze → L5", "act_l5_set", captures_job_id=True)
            Button(label="Refresh", on_click=[_refresh_panel])
        if data.get("source_playlist_id"):
            with Row(gap=2):
                Button(
                    label="Sync diff → YM",
                    on_click=[
                        CallTool(
                            "playlist_sync",
                            arguments={
                                "playlist_id": data["source_playlist_id"],
                                "direction": "diff",
                            },
                            on_success=ShowToast(
                                message="YM diff computed — see tool result",
                                variant="success",
                            ),
                            on_error=ShowToast(message="{{ $error }}", variant="error"),
                        ),
                    ],
                )
        with Slot("panel"):
            Muted("Run an action to see render status.")

    return PrefabApp(
        view=view,
        state={
            "version_id": vid,
            "job_id": "",
            "panel": _panel_fragment(data).to_json(),
        },
    )
