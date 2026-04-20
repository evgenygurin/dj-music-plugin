"""ui_camelot_wheel — Prefab Camelot wheel view.

Renders a RadialChart of tracks placed around the 24-slot wheel (minor keys
inner, major keys outer conceptually) + a DataTable with slot counts. Reuses
``app/domain/camelot/wheel.py`` key math and the palette constants in
``app/shared/ui_colors.py``.
"""

from __future__ import annotations

from collections import Counter
from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.domain.camelot.wheel import key_code_to_camelot
from app.models.track_features import TrackAudioFeaturesComputed
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import get_uow
from app.shared.errors import NotFoundError
from app.shared.ui_colors import CAMELOT_WHEEL_COLORS
from app.tools.ui._fallback import (
    CamelotWheelFallback,
    CamelotWheelSlot,
    fallback_or,
    supports_ui,
)
from app.tools.ui._prefab import (
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
    RadialChart,
    Row,
)


async def _track_ids_for_scope(uow: UnitOfWork, playlist_id: int | None) -> list[int]:
    if playlist_id is None:
        page = await uow.tracks.filter(limit=10000)
        return [r.id for r in page.items]
    if await uow.playlists.get(playlist_id) is None:
        raise NotFoundError("playlist", playlist_id)
    return await uow.playlists.get_track_ids(playlist_id)


async def _gather(uow: UnitOfWork, playlist_id: int | None) -> dict[str, Any]:
    track_ids = await _track_ids_for_scope(uow, playlist_id)
    if not track_ids:
        return {"playlist_id": playlist_id, "total_tracks": 0, "slots": []}

    from sqlalchemy import select

    stmt = select(
        TrackAudioFeaturesComputed.track_id,
        TrackAudioFeaturesComputed.key_code,
    ).where(TrackAudioFeaturesComputed.track_id.in_(track_ids))
    rows = (await uow.track_features.session.execute(stmt)).all()

    slot_counts: Counter[int] = Counter()
    for _tid, key_code in rows:
        if key_code is None:
            continue
        slot_counts[int(key_code)] += 1

    slots: list[CamelotWheelSlot] = []
    for code in range(24):
        try:
            notation = key_code_to_camelot(code)
        except ValueError:
            continue
        slots.append(
            CamelotWheelSlot(
                camelot=notation,
                key_code=code,
                track_count=slot_counts.get(code, 0),
            )
        )
    slots.sort(key=lambda s: (s.camelot[-1], int(s.camelot[:-1])))

    return {
        "playlist_id": playlist_id,
        "total_tracks": len(track_ids),
        "slots": slots,
    }


@tool(
    name="ui_camelot_wheel",
    tags={"namespace:ui:read", "ui", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    meta={"ui": True, "timeout_s": 30.0},
    description=(
        "Prefab Camelot wheel: tracks-per-slot RadialChart + DataTable. Scope: "
        "a playlist when playlist_id is given, otherwise the full library."
    ),
    timeout=30.0,
)
async def ui_camelot_wheel(
    playlist_id: Annotated[
        int | None, Field(description="Playlist ID; None = whole library (first 10000 tracks)")
    ] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> Column | CamelotWheelFallback:
    data = await _gather(uow, playlist_id)

    if not supports_ui(ctx):
        return fallback_or(CamelotWheelFallback, data)

    radial_rows = [
        {
            "name": s.camelot,
            "count": s.track_count,
            "color": CAMELOT_WHEEL_COLORS.get(s.camelot, "#64748b"),
        }
        for s in data["slots"]
    ]
    table_rows = [
        {
            "camelot": s.camelot,
            "key_code": s.key_code,
            "count": s.track_count,
        }
        for s in data["slots"]
    ]

    with Column(gap=4, css_class="p-6") as view:
        Heading(
            f"Camelot Wheel · playlist {playlist_id}"
            if playlist_id is not None
            else "Camelot Wheel · library"
        )
        with Row(gap=4):
            Metric(label="Tracks in scope", value=str(data["total_tracks"]))
            Metric(
                label="Distinct keys",
                value=str(sum(1 for s in data["slots"] if s.track_count > 0)),
            )
        if radial_rows and any(r["count"] for r in radial_rows):
            with Card():
                CardHeader(children=[CardTitle("Wheel")])
                CardContent(
                    children=[
                        RadialChart(
                            data=radial_rows,
                            data_key="count",
                            name_key="name",
                            inner_radius=40,
                            show_legend=True,
                            height=320,
                        ),
                    ]
                )
        else:
            Muted("No tracks with key_code in scope.")
        if table_rows:
            DataTable(
                rows=table_rows,
                columns=[
                    DataTableColumn(key="camelot", header="Camelot", sortable=True, width="100px"),
                    DataTableColumn(
                        key="key_code", header="Key code", sortable=True, width="100px"
                    ),
                    DataTableColumn(key="count", header="Tracks", sortable=True, align="right"),
                ],
                paginated=False,
            )
    return view
