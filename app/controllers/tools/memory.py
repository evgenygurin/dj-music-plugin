"""AI memory tools — 5 action-dispatch tools (tag: memory, hidden by default).

Consolidates 19 individual tools from track_feedback, transition_history,
track_affinity, scoring_profile, and adaptive_arc into 5 dispatched tools.

Unlock via ``unlock_tools(action="unlock", category="memory")``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies.db import get_db_session
from app.controllers.dependencies.services import get_transition_history_service
from app.controllers.tools._shared.errors import map_domain_errors
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE_IDEMPOTENT,
    ICON_MEMORY,
    TOOL_META,
    ToolCategory,
)
from app.db.models.scoring_profile import ScoringProfile
from app.db.repositories.track_affinity import TrackAffinityRepository
from app.db.repositories.track_feedback import TrackFeedbackRepository
from app.db.repositories.transition_history import TransitionHistoryRepository
from app.schemas.track_affinity import AffinityRecommendation
from app.schemas.track_feedback import TrackFeedbackRead
from app.schemas.transition_history import BestPairRead, TransitionHistoryRead
from app.services.adaptive_arc import AdaptiveArcService
from app.services.track_affinity import TrackAffinityService
from app.services.transition_history import TransitionHistoryService

# ---------------------------------------------------------------------------
# DI factories
# ---------------------------------------------------------------------------


def _get_feedback_repo(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> TrackFeedbackRepository:
    return TrackFeedbackRepository(session)


def _get_affinity_svc(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> TrackAffinityService:
    return TrackAffinityService(TrackAffinityRepository(session))


def _get_arc_svc(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> AdaptiveArcService:
    return AdaptiveArcService(TransitionHistoryRepository(session))


def _get_session(
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> AsyncSession:
    return session


# ═══════════════════════════════════════════════════════════════════════════
# 1. track_feedback  (was: like_track, ban_track, rate_track,
#    get_track_feedback, get_banned_tracks, get_liked_tracks)
# ═══════════════════════════════════════════════════════════════════════════

TrackFeedbackAction = Literal["like", "ban", "rate", "get", "list_liked", "list_banned"]


@tool(
    title="Track Feedback",
    tags={ToolCategory.MEMORY.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_MEMORY,
    meta=TOOL_META,
)
@map_domain_errors
async def track_feedback(
    action: Annotated[TrackFeedbackAction, Field(description="Feedback operation")],
    track_id: Annotated[
        int | None, Field(description="Local track ID (required for like/ban/rate/get)")
    ] = None,
    rating: Annotated[
        int | None, Field(description="Rating 1-5 (required for rate)", ge=1, le=5)
    ] = None,
    notes: Annotated[str | None, Field(description="Freeform notes (optional for rate)")] = None,
    repo: TrackFeedbackRepository = Depends(_get_feedback_repo),  # noqa: B008
) -> dict[str, object] | list[int] | TrackFeedbackRead:
    """Manage per-track feedback: like, ban, rate, or query feedback state.
    Use when recording DJ preferences or retrieving liked/banned lists for set building.
    """
    if action in ("like", "ban", "rate", "get") and track_id is None:
        raise ToolError(f"track_id required for action={action}")

    if action == "like":
        entry = await repo.upsert(track_id, status="liked", rating=5)  # type: ignore[arg-type]
        return TrackFeedbackRead.model_validate(entry)

    if action == "ban":
        entry = await repo.upsert(track_id, status="banned", rating=1)  # type: ignore[arg-type]
        return TrackFeedbackRead.model_validate(entry)

    if action == "rate":
        if rating is None:
            raise ToolError("rating required for action=rate")
        entry = await repo.upsert(track_id, rating=rating, notes=notes)  # type: ignore[arg-type]
        return TrackFeedbackRead.model_validate(entry)

    if action == "get":
        fb = await repo.get_by_track(track_id)  # type: ignore[arg-type]
        if fb is None:
            return {"found": False, "track_id": track_id}
        return {"found": True, **TrackFeedbackRead.model_validate(fb).model_dump()}

    if action == "list_liked":
        return await repo.get_liked_ids()

    # action == "list_banned"
    return await repo.get_banned_ids()


# ═══════════════════════════════════════════════════════════════════════════
# 2. transition_history  (was: log_transition, get_transition_history,
#    get_best_pairs, update_reaction)
# ═══════════════════════════════════════════════════════════════════════════

TransitionAction = Literal["log", "list", "best_pairs", "react"]


@tool(
    title="Transition History",
    tags={ToolCategory.MEMORY.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_MEMORY,
    meta=TOOL_META,
)
@map_domain_errors
async def transition_history(
    action: Annotated[TransitionAction, Field(description="Operation to perform")],
    from_track_id: Annotated[
        int | None,
        Field(description="Source track ID (required for log, optional filter for list)"),
    ] = None,
    to_track_id: Annotated[
        int | None,
        Field(description="Destination track ID (required for log, optional filter for list)"),
    ] = None,
    track_id: Annotated[int | None, Field(description="Track ID for best_pairs lookup")] = None,
    entry_id: Annotated[
        int | None, Field(description="Transition entry ID (required for react)")
    ] = None,
    reaction: Annotated[
        Literal["like", "skip", "ban", "listened"] | None,
        Field(description="User reaction (required for react)"),
    ] = None,
    overall_score: Annotated[float | None, Field(description="Aggregate transition score")] = None,
    bpm_score: Annotated[float | None, Field(description="BPM compatibility score")] = None,
    harmonic_score: Annotated[
        float | None, Field(description="Harmonic compatibility score")
    ] = None,
    energy_score: Annotated[float | None, Field(description="Energy continuity score")] = None,
    spectral_score: Annotated[float | None, Field(description="Spectral similarity score")] = None,
    groove_score: Annotated[float | None, Field(description="Groove alignment score")] = None,
    timbral_score: Annotated[float | None, Field(description="Timbral similarity score")] = None,
    style: Annotated[str | None, Field(description="Transition style name")] = None,
    duration_sec: Annotated[
        float | None, Field(description="Crossfade duration (seconds)")
    ] = None,
    tempo_match_ratio: Annotated[
        float | None, Field(description="Beat grid alignment ratio")
    ] = None,
    user_reaction: Annotated[
        str | None, Field(description="Reaction for log: like/skip/ban/listened")
    ] = None,
    session_id: Annotated[str | None, Field(description="Session identifier for grouping")] = None,
    limit: Annotated[int, Field(description="Max results to return")] = 20,
    min_score: Annotated[
        float | None, Field(description="Min overall score filter (list)")
    ] = None,
    svc: TransitionHistoryService = Depends(get_transition_history_service),  # noqa: B008
) -> TransitionHistoryRead | list[TransitionHistoryRead] | list[BestPairRead] | dict[str, str]:
    """Record, query, and react to crossfade transitions between tracks.
    Use when logging transitions during a session, browsing history, finding best partners, or adding feedback.
    """
    if action == "log":
        if from_track_id is None or to_track_id is None:
            raise ToolError("from_track_id and to_track_id required for action=log")
        entry = await svc.log_transition(
            from_track_id=from_track_id,
            to_track_id=to_track_id,
            overall_score=overall_score,
            bpm_score=bpm_score,
            harmonic_score=harmonic_score,
            energy_score=energy_score,
            spectral_score=spectral_score,
            groove_score=groove_score,
            timbral_score=timbral_score,
            style=style,
            duration_sec=duration_sec,
            tempo_match_ratio=tempo_match_ratio,
            user_reaction=user_reaction,
            session_id=session_id,
        )
        return TransitionHistoryRead.model_validate(entry)

    if action == "list":
        entries = await svc.get_history(from_track_id, to_track_id, limit, min_score)
        return [TransitionHistoryRead.model_validate(e) for e in entries]

    if action == "best_pairs":
        if track_id is None:
            raise ToolError("track_id required for action=best_pairs")
        pairs = await svc.get_best_pairs(track_id, limit)
        return [BestPairRead.model_validate(p) for p in pairs]

    # action == "react"
    if entry_id is None or reaction is None:
        raise ToolError("entry_id and reaction required for action=react")
    await svc.update_reaction(entry_id, reaction)
    return {"status": "ok", "reaction": reaction}


# ═══════════════════════════════════════════════════════════════════════════
# 3. track_affinity  (was: refresh_affinity, get_track_affinity,
#    get_affinity_recommendations)
# ═══════════════════════════════════════════════════════════════════════════

AffinityAction = Literal["refresh", "get_pair", "recommend"]


@tool(
    title="Track Affinity",
    tags={ToolCategory.MEMORY.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_MEMORY,
    meta=TOOL_META,
)
@map_domain_errors
async def track_affinity(
    action: Annotated[AffinityAction, Field(description="Affinity operation")],
    track_id: Annotated[int | None, Field(description="Track ID for recommend action")] = None,
    track_a_id: Annotated[
        int | None, Field(description="First track ID (required for get_pair)")
    ] = None,
    track_b_id: Annotated[
        int | None, Field(description="Second track ID (required for get_pair)")
    ] = None,
    limit: Annotated[int, Field(description="Max recommendations (for recommend)")] = 10,
    svc: TrackAffinityService = Depends(_get_affinity_svc),  # noqa: B008
) -> dict[str, object] | list[AffinityRecommendation]:
    """Manage track affinity data derived from transition history.
    Use when rebuilding the affinity matrix, checking pair chemistry, or getting track recommendations.
    """
    if action == "refresh":
        count = await svc.refresh()
        return {"pairs_updated": count}

    if action == "get_pair":
        if track_a_id is None or track_b_id is None:
            raise ToolError("track_a_id and track_b_id required for action=get_pair")
        result = await svc.get_pair(track_a_id, track_b_id)
        if result is None:
            return {"found": False, "track_a_id": track_a_id, "track_b_id": track_b_id}
        return {"found": True, **result}

    # action == "recommend"
    if track_id is None:
        raise ToolError("track_id required for action=recommend")
    pairs = await svc.get_recommendations(track_id, limit)
    return [AffinityRecommendation.model_validate(p) for p in pairs]


# ═══════════════════════════════════════════════════════════════════════════
# 4. scoring_profile  (was: create_scoring_profile, list_scoring_profiles,
#    get_scoring_weights)
# ═══════════════════════════════════════════════════════════════════════════

ScoringAction = Literal["create", "list", "get_weights"]


@tool(
    title="Scoring Profile",
    tags={ToolCategory.MEMORY.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_MEMORY,
    meta=TOOL_META,
)
@map_domain_errors
async def scoring_profile(
    action: Annotated[ScoringAction, Field(description="Profile operation")],
    name: Annotated[
        str | None,
        Field(description="Profile name (required for create, optional for get_weights)"),
    ] = None,
    bpm_weight: Annotated[float, Field(description="BPM weight (sum ~1.0)", ge=0, le=1)] = 0.20,
    harmonic_weight: Annotated[float, Field(description="Harmonic weight", ge=0, le=1)] = 0.12,
    energy_weight: Annotated[float, Field(description="Energy weight", ge=0, le=1)] = 0.18,
    spectral_weight: Annotated[float, Field(description="Spectral weight", ge=0, le=1)] = 0.20,
    groove_weight: Annotated[float, Field(description="Groove weight", ge=0, le=1)] = 0.15,
    timbral_weight: Annotated[float, Field(description="Timbral weight", ge=0, le=1)] = 0.15,
    description: Annotated[str | None, Field(description="Profile description")] = None,
    session: AsyncSession = Depends(_get_session),  # noqa: B008
) -> dict[str, object] | list[dict[str, object]]:
    """Manage personal scoring weight profiles for the 6-component transition formula.
    Use when creating custom scoring preferences or retrieving weights for score_transitions.
    """
    if action == "create":
        if not name:
            raise ToolError("name required for action=create")
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

    if action == "list":
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

    # action == "get_weights"
    profile_name = name or "default"
    result = await session.execute(
        select(ScoringProfile).where(ScoringProfile.name == profile_name)
    )
    found = result.scalar_one_or_none()
    if found is None:
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
        "profile": found.name,
        "found": True,
        "weights": {
            "bpm": found.bpm_weight,
            "harmonic": found.harmonic_weight,
            "energy": found.energy_weight,
            "spectral": found.spectral_weight,
            "groove": found.groove_weight,
            "timbral": found.timbral_weight,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# 5. session_arc  (was: get_energy_trend, suggest_energy_direction,
#    get_session_arc)
# ═══════════════════════════════════════════════════════════════════════════

SessionArcAction = Literal["trend", "suggest", "full_arc"]


@tool(
    title="Session Arc",
    tags={ToolCategory.MEMORY.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_MEMORY,
    meta=TOOL_META,
)
@map_domain_errors
async def session_arc(
    action: Annotated[SessionArcAction, Field(description="Arc analysis operation")],
    last_n: Annotated[int, Field(description="Recent transitions to analyze", ge=1)] = 10,
    limit: Annotated[int, Field(description="Max transitions for full_arc", ge=1)] = 50,
    svc: AdaptiveArcService = Depends(_get_arc_svc),  # noqa: B008
) -> dict[str, Any] | list[dict[str, Any]]:
    """Analyze session energy arc from transition history.
    Use when deciding energy direction for the next track or reviewing the session flow.
    """
    if action == "trend":
        trend = await svc.get_energy_trend(last_n)
        return {"trend": trend}

    if action == "suggest":
        return await svc.suggest_energy_direction(last_n)

    # action == "full_arc"
    return await svc.compute_preferred_arc(limit=limit)
