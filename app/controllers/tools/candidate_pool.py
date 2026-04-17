"""Candidate pool exploration tool.

Tools:
- get_candidate_pool — explore the library before committing to build_set
"""

from typing import Annotated, Literal

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies import get_db_session
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ICON_TRACKS,
    TOOL_META,
    ToolCategory,
)
from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.track import Track
from app.schemas.tool_output import CandidatePoolTrackRow, GetCandidatePoolResult

_ENERGY_LEVEL_LUFS: dict[str, tuple[float | None, float | None]] = {
    "low": (None, -13.0),
    "mid": (-13.0, -11.0),
    "high": (-11.0, None),
}


@tool(
    title="Get Candidate Pool",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_TRACKS,
    meta=TOOL_META,
)
async def get_candidate_pool(
    description: Annotated[
        str | None,
        Field(
            description="Natural language description (e.g. 'dark hypnotic tracks'). Informational — use other params for filtering."
        ),
    ] = None,
    subgenres: Annotated[
        list[str] | None,
        Field(description="Filter by subgenre/mood (e.g. ['detroit', 'industrial'])"),
    ] = None,
    bpm_min: Annotated[float | None, Field(description="Minimum BPM")] = None,
    bpm_max: Annotated[float | None, Field(description="Maximum BPM")] = None,
    energy_level: Annotated[
        Literal["low", "mid", "high"] | None,
        Field(description="Energy tier: low (LUFS < -13), mid (-13 to -11), high (> -11)"),
    ] = None,
    lufs_min: Annotated[
        float | None,
        Field(description="Minimum integrated LUFS (overrides energy_level lower bound)"),
    ] = None,
    lufs_max: Annotated[
        float | None,
        Field(description="Maximum integrated LUFS (overrides energy_level upper bound)"),
    ] = None,
    limit: Annotated[int, Field(description="Max tracks to return", ge=1, le=200)] = 50,
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> GetCandidatePoolResult:
    """Explore library tracks matching criteria without creating a set.

    Use this before build_set to: verify enough tracks exist for a subgenre,
    sample the candidate pool by BPM/energy, or check track quality distribution.
    Does not write anything to the database.
    """
    stmt = (
        select(Track, TrackAudioFeaturesComputed)
        .join(TrackAudioFeaturesComputed, TrackAudioFeaturesComputed.track_id == Track.id)
        .where(Track.status == 0)
    )

    if subgenres:
        stmt = stmt.where(TrackAudioFeaturesComputed.mood.in_(subgenres))

    if bpm_min is not None:
        stmt = stmt.where(TrackAudioFeaturesComputed.bpm >= bpm_min)
    if bpm_max is not None:
        stmt = stmt.where(TrackAudioFeaturesComputed.bpm <= bpm_max)

    # LUFS bounds: explicit params override per-boundary; missing bound falls back to tier
    effective_lufs_min = lufs_min
    effective_lufs_max = lufs_max
    if energy_level is not None:
        tier_min, tier_max = _ENERGY_LEVEL_LUFS[energy_level]
        if effective_lufs_min is None:
            effective_lufs_min = tier_min
        if effective_lufs_max is None:
            effective_lufs_max = tier_max

    if effective_lufs_min is not None:
        stmt = stmt.where(TrackAudioFeaturesComputed.integrated_lufs >= effective_lufs_min)
    if effective_lufs_max is not None:
        stmt = stmt.where(TrackAudioFeaturesComputed.integrated_lufs <= effective_lufs_max)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(TrackAudioFeaturesComputed.bpm).limit(limit)
    rows = (await session.execute(stmt)).all()

    tracks = [
        CandidatePoolTrackRow(
            id=track.id,
            title=track.title,
            bpm=features.bpm,
            mood=features.mood,
            energy_lufs=features.integrated_lufs,
            key_code=features.key_code,
        )
        for track, features in rows
    ]

    return GetCandidatePoolResult(
        tracks=tracks,
        total=int(total),
        returned=len(tracks),
        filters_applied={
            "description": description,
            "subgenres": subgenres,
            "bpm_min": bpm_min,
            "bpm_max": bpm_max,
            "energy_level": energy_level,
            "lufs_min": effective_lufs_min,
            "lufs_max": effective_lufs_max,
        },
    )
