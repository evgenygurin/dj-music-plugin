"""Library preparation readiness resource."""

from __future__ import annotations

from fastmcp.dependencies import Depends
from fastmcp.resources import ResourceResult, resource
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies import get_db_session
from app.controllers.resources._shared import json_resource
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_RESOURCE,
    RESOURCE_META,
    RESOURCE_VERSION,
)
from app.db.models.library import (
    DjBeatgrid,
    DjBeatgridChangePoint,
    DjCuePoint,
    DjLibraryItem,
    DjSavedLoop,
)


@resource(
    uri="library://prep-state",
    name="Library Prep State",
    title="Library Prep State",
    description="Readiness metrics for beatgrids, cues, loops, and file metadata in DJ library",
    mime_type="application/json",
    tags={"core"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_RESOURCE,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def library_prep_state(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
    """Return DJ library preparation readiness metrics."""
    total_items = (await session.execute(select(func.count(DjLibraryItem.id)))).scalar() or 0

    with_beatgrid = (
        await session.execute(select(func.count(func.distinct(DjBeatgrid.library_item_id))))
    ).scalar() or 0
    with_canonical_beatgrid = (
        await session.execute(
            select(func.count(func.distinct(DjBeatgrid.library_item_id))).where(
                DjBeatgrid.canonical.is_(True)
            )
        )
    ).scalar() or 0
    with_variable_tempo_beatgrid = (
        await session.execute(
            select(func.count(func.distinct(DjBeatgrid.library_item_id))).where(
                DjBeatgrid.variable_tempo.is_(True)
            )
        )
    ).scalar() or 0
    with_beatgrid_change_points = (
        await session.execute(
            select(func.count(func.distinct(DjBeatgrid.library_item_id)))
            .select_from(DjBeatgrid)
            .join(DjBeatgridChangePoint, DjBeatgridChangePoint.beatgrid_id == DjBeatgrid.id)
        )
    ).scalar() or 0

    with_cues = (
        await session.execute(select(func.count(func.distinct(DjCuePoint.library_item_id))))
    ).scalar() or 0
    with_loops = (
        await session.execute(select(func.count(func.distinct(DjSavedLoop.library_item_id))))
    ).scalar() or 0

    metadata_row = (
        await session.execute(
            select(
                func.count(DjLibraryItem.id)
                .filter(DjLibraryItem.mime_type.isnot(None))
                .label("with_mime_type"),
                func.count(DjLibraryItem.id)
                .filter(DjLibraryItem.bitrate.isnot(None))
                .label("with_bitrate"),
                func.count(DjLibraryItem.id)
                .filter(DjLibraryItem.sample_rate.isnot(None))
                .label("with_sample_rate"),
                func.count(DjLibraryItem.id)
                .filter(DjLibraryItem.channels.isnot(None))
                .label("with_channels"),
                func.count(DjLibraryItem.id)
                .filter(DjLibraryItem.file_uri.isnot(None))
                .label("with_file_uri"),
            )
        )
    ).one()

    source_rows = await session.execute(
        select(DjLibraryItem.source_app, func.count(DjLibraryItem.id))
        .group_by(DjLibraryItem.source_app)
        .order_by(func.count(DjLibraryItem.id).desc())
    )
    by_source_app = {(source_app or "unknown"): int(count) for source_app, count in source_rows}

    def _pct(value: int) -> float:
        return round((value / total_items * 100), 2) if total_items else 0.0

    data = {
        "totals": {
            "library_items": total_items,
            "with_any_beatgrid": with_beatgrid,
            "with_canonical_beatgrid": with_canonical_beatgrid,
            "with_variable_tempo_beatgrid": with_variable_tempo_beatgrid,
            "with_beatgrid_change_points": with_beatgrid_change_points,
            "with_cue_points": with_cues,
            "with_saved_loops": with_loops,
        },
        "coverage_pct": {
            "with_any_beatgrid": _pct(with_beatgrid),
            "with_canonical_beatgrid": _pct(with_canonical_beatgrid),
            "with_cue_points": _pct(with_cues),
            "with_saved_loops": _pct(with_loops),
        },
        "file_metadata": {
            "with_mime_type": int(metadata_row.with_mime_type or 0),
            "with_bitrate": int(metadata_row.with_bitrate or 0),
            "with_sample_rate": int(metadata_row.with_sample_rate or 0),
            "with_channels": int(metadata_row.with_channels or 0),
            "with_file_uri": int(metadata_row.with_file_uri or 0),
        },
        "source_app_distribution": by_source_app,
    }
    return json_resource(data)
