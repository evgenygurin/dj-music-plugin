"""MCP tools — personal scoring weights (Phase 6)."""

from __future__ import annotations

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies.db import get_db_session
from app.controllers.tools._shared.errors import map_domain_errors
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_MEMORY,
    TOOL_META,
    ToolCategory,
)
from app.db.models.scoring_profile import ScoringProfile


def _get_session(session: AsyncSession = Depends(get_db_session)) -> AsyncSession:  # noqa: B008
    return session


@tool(
    title="Create Scoring Profile",
    tags={ToolCategory.CORE.value, "memory"},
    icons=ICON_MEMORY,
    meta=TOOL_META,
)
@map_domain_errors
async def create_scoring_profile(
    name: str,
    bpm_weight: float = 0.20,
    harmonic_weight: float = 0.12,
    energy_weight: float = 0.18,
    spectral_weight: float = 0.20,
    groove_weight: float = 0.15,
    timbral_weight: float = 0.15,
    description: str | None = None,
    session: AsyncSession = Depends(_get_session),
) -> dict:
    """Create a personal scoring weight profile.

    Weights control how the 6-component transition formula is balanced.
    Higher weight = more influence on the overall score.
    All weights should sum to ~1.0 for best results.

    Presets:
    - "default": balanced (0.20/0.12/0.18/0.20/0.15/0.15)
    - "groove_lover": groove-heavy (bpm 0.15, groove 0.30, timbral 0.20)
    - "harmonic_purist": key-focused (harmonic 0.30, spectral 0.10)
    """
    profile = ScoringProfile(
        name=name,
        bpm_weight=bpm_weight,
        harmonic_weight=harmonic_weight,
        energy_weight=energy_weight,
        spectral_weight=spectral_weight,
        groove_weight=groove_weight,
        timbral_weight=timbral_weight,
        description=description,
    )
    session.add(profile)
    await session.flush()
    return {
        "id": profile.id,
        "name": profile.name,
        "weights": {
            "bpm": profile.bpm_weight,
            "harmonic": profile.harmonic_weight,
            "energy": profile.energy_weight,
            "spectral": profile.spectral_weight,
            "groove": profile.groove_weight,
            "timbral": profile.timbral_weight,
        },
    }


@tool(
    title="List Scoring Profiles",
    tags={ToolCategory.CORE.value, "memory"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_MEMORY,
    meta=TOOL_META,
)
@map_domain_errors
async def list_scoring_profiles(
    session: AsyncSession = Depends(_get_session),
) -> list[dict]:
    """List all personal scoring weight profiles."""
    result = await session.execute(select(ScoringProfile).order_by(ScoringProfile.name))
    profiles = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "weights": {
                "bpm": p.bpm_weight,
                "harmonic": p.harmonic_weight,
                "energy": p.energy_weight,
                "spectral": p.spectral_weight,
                "groove": p.groove_weight,
                "timbral": p.timbral_weight,
            },
            "description": p.description,
        }
        for p in profiles
    ]


@tool(
    title="Get Scoring Weights",
    tags={ToolCategory.CORE.value, "memory"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_MEMORY,
    meta=TOOL_META,
)
@map_domain_errors
async def get_scoring_weights(
    profile_name: str = "default",
    session: AsyncSession = Depends(_get_session),
) -> dict:
    """Get scoring weights for a named profile.

    Returns weights dict for use with score_transitions.
    Falls back to default weights if profile not found.
    """
    result = await session.execute(
        select(ScoringProfile).where(ScoringProfile.name == profile_name)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        return {
            "profile": "default",
            "found": False,
            "weights": {
                "bpm": 0.20,
                "harmonic": 0.12,
                "energy": 0.18,
                "spectral": 0.20,
                "groove": 0.15,
                "timbral": 0.15,
            },
        }
    return {
        "profile": profile.name,
        "found": True,
        "weights": {
            "bpm": profile.bpm_weight,
            "harmonic": profile.harmonic_weight,
            "energy": profile.energy_weight,
            "spectral": profile.spectral_weight,
            "groove": profile.groove_weight,
            "timbral": profile.timbral_weight,
        },
    }
