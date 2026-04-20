"""ui_set_view — Prefab dashboard for a DJ set.

Renders energy arc (LineChart), track DataTable, transition badges, and
a cheatsheet card. Reuses ``app/resources/set.py`` gather helpers via the
same repository accessors.
"""

from __future__ import annotations

import itertools
from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from prefab_ui.components import (
    Badge,
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
)
from prefab_ui.components.charts import ChartSeries, LineChart
from pydantic import Field

from app.domain.camelot.wheel import key_code_to_camelot
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow
from app.shared.errors import NotFoundError
from app.shared.ui_colors import score_color
from app.tools.ui._fallback import (
    EnergyPoint,
    SetViewFallback,
    TrackRow,
    TransitionEdge,
    fallback_or,
    supports_ui,
)


async def _gather(uow: UnitOfWork, set_id: int, version_id: int | None) -> dict[str, Any]:
    s = await uow.sets.get(set_id)
    if s is None:
        raise NotFoundError("set", set_id)

    if version_id is not None:
        ver = await uow.set_versions.get(version_id)
        if ver is None or getattr(ver, "set_id", None) != set_id:
            raise NotFoundError("set_version", version_id)
    else:
        ver = await uow.set_versions.get_latest(set_id)

    items = await uow.set_versions.get_items(ver.id) if ver is not None else []
    items = sorted(items, key=lambda i: getattr(i, "sort_index", 0))

    track_ids = [it.track_id for it in items]

    # Three batched DB roundtrips replace the previous N+1 (one tracks.get +
    # one transitions.get_pair per item). Order matters only for the final
    # render — we look everything up by id below.
    feat_map = await uow.track_features.get_scoring_features_batch(track_ids)
    track_map = await uow.tracks.get_many(track_ids)
    pair_keys = list(itertools.pairwise(track_ids))
    pair_map = await uow.transitions.get_pairs_batch(pair_keys)

    rows: list[TrackRow] = []
    energy: list[EnergyPoint] = []
    for it in items:
        tid = it.track_id
        track = track_map.get(tid)
        feat = feat_map.get(tid)
        key_code = getattr(feat, "key_code", None)
        rows.append(
            TrackRow(
                position=int(getattr(it, "sort_index", 0) or 0),
                track_id=tid,
                title=getattr(track, "title", None) if track else None,
                bpm=getattr(feat, "bpm", None),
                key_code=key_code,
                camelot=key_code_to_camelot(key_code) if key_code is not None else None,
                lufs=getattr(feat, "integrated_lufs", None),
                mood=getattr(feat, "mood", None),
            )
        )
        energy.append(
            EnergyPoint(
                position=int(getattr(it, "sort_index", 0) or 0),
                lufs=getattr(feat, "integrated_lufs", None),
            )
        )

    transitions: list[TransitionEdge] = []
    for pos, (a, b) in enumerate(pair_keys):
        tr = pair_map.get((a, b))
        transitions.append(
            TransitionEdge(
                position=pos + 1,
                from_track_id=a,
                to_track_id=b,
                overall=getattr(tr, "overall_quality", None) if tr else None,
                hard_reject=bool(getattr(tr, "hard_reject", False)) if tr else None,
            )
        )

    return {
        "set_id": set_id,
        "name": getattr(s, "name", None),
        "template_name": getattr(s, "template_name", None),
        "version_id": getattr(ver, "id", None) if ver is not None else None,
        "quality_score": getattr(ver, "quality_score", None) if ver is not None else None,
        "tracks": rows,
        "energy_arc": energy,
        "transitions": transitions,
    }


def _badge_variant(score: float | None) -> str:
    if score is None:
        return "secondary"
    if score >= 0.75:
        return "default"
    if score >= 0.5:
        return "outline"
    return "destructive"


@tool(
    name="ui_set_view",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": True},
    description=(
        "Prefab dashboard for a DJ set: energy arc (LineChart), track table, "
        "transition badges, cheatsheet card. Fallback: JSON payload."
    ),
)
async def ui_set_view(
    set_id: Annotated[int, Field(description="DJ set ID")],
    version_id: Annotated[
        int | None, Field(description="Specific set version (default: latest)")
    ] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> Column | SetViewFallback:
    data = await _gather(uow, set_id, version_id)

    if not supports_ui(ctx):
        return fallback_or(SetViewFallback, data)

    rows = [r.model_dump() for r in data["tracks"]]
    energy_points = [{"position": p.position, "lufs": p.lufs or 0.0} for p in data["energy_arc"]]

    with Column(gap=4, css_class="p-6") as view:
        Heading(f"{data['name'] or f'Set #{set_id}'}")
        Muted(
            f"template={data['template_name'] or 'ad-hoc'} · "
            f"tracks={len(rows)} · quality={data['quality_score'] or 0.0:.2f}"
        )
        if energy_points:
            LineChart(
                data=energy_points,
                series=[ChartSeries(data_key="lufs", label="LUFS", color="#34d399")],
                x_axis="position",
                show_grid=True,
                show_legend=False,
                height=220,
            )
        if rows:
            DataTable(
                rows=rows,
                columns=[
                    DataTableColumn(key="position", header="#", sortable=True, width="48px"),
                    DataTableColumn(key="title", header="Title", sortable=True),
                    DataTableColumn(key="bpm", header="BPM", sortable=True, width="80px"),
                    DataTableColumn(key="camelot", header="Key", width="64px"),
                    DataTableColumn(key="lufs", header="LUFS", sortable=True, width="80px"),
                    DataTableColumn(key="mood", header="Mood"),
                ],
                paginated=len(rows) > 25,
                page_size=25,
            )
        if data["transitions"]:
            with Row(gap=2, css_class="flex-wrap"):
                for edge in data["transitions"]:
                    score = edge.overall
                    label = f"{edge.from_track_id}→{edge.to_track_id}"
                    if edge.hard_reject:
                        label += " ⚠"
                    elif score is not None:
                        label += f" {score:.2f}"
                    Badge(label=label, variant=_badge_variant(score))
        with Card():
            CardHeader(children=[CardTitle("Cheatsheet")])
            CardContent(
                children=[
                    Muted(
                        f"Hard conflicts: {sum(1 for e in data['transitions'] if e.hard_reject)}"
                    ),
                    Muted(f"Avg score: {_avg([e.overall for e in data['transitions']]):.2f}"),
                ]
            )
    # Anchor score_color usage (kept for parity with library_audit palette)
    _ = score_color(0.5)
    return view


def _avg(xs: list[float | None]) -> float:
    vals = [x for x in xs if x is not None]
    return sum(vals) / len(vals) if vals else 0.0
