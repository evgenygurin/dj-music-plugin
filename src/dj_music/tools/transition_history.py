"""MCP tools — transition history (AI set builder memory)."""

from __future__ import annotations

from fastmcp.dependencies import Depends
from fastmcp.tools import tool

from app.controllers.dependencies.services import get_transition_history_service
from dj_music.tools._shared.errors import map_domain_errors
from dj_music.tools._shared.taxonomy import ANNOTATIONS_READ_ONLY, ToolCategory
from dj_music.schemas.transition_history import BestPairRead, TransitionHistoryRead
from dj_music.services.transition_history import TransitionHistoryService


@tool(tags={ToolCategory.CORE.value, "memory"})
@map_domain_errors
async def log_transition(
    from_track_id: int,
    to_track_id: int,
    overall_score: float | None = None,
    bpm_score: float | None = None,
    harmonic_score: float | None = None,
    energy_score: float | None = None,
    spectral_score: float | None = None,
    groove_score: float | None = None,
    timbral_score: float | None = None,
    style: str | None = None,
    duration_sec: float | None = None,
    tempo_match_ratio: float | None = None,
    user_reaction: str | None = None,
    session_id: str | None = None,
    svc: TransitionHistoryService = Depends(get_transition_history_service),  # noqa: B008
) -> TransitionHistoryRead:
    """Record a completed crossfade transition for learning."""
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


@tool(tags={ToolCategory.CORE.value, "memory"}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def get_transition_history(
    from_track_id: int | None = None,
    to_track_id: int | None = None,
    limit: int = 20,
    min_score: float | None = None,
    svc: TransitionHistoryService = Depends(get_transition_history_service),  # noqa: B008
) -> list[TransitionHistoryRead]:
    """Query past transitions with optional filters."""
    entries = await svc.get_history(from_track_id, to_track_id, limit, min_score)
    return [TransitionHistoryRead.model_validate(e) for e in entries]


@tool(tags={ToolCategory.CORE.value, "memory"}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def get_best_pairs(
    track_id: int,
    limit: int = 10,
    svc: TransitionHistoryService = Depends(get_transition_history_service),  # noqa: B008
) -> list[BestPairRead]:
    """Top-N best historical transition partners for a track."""
    pairs = await svc.get_best_pairs(track_id, limit)
    return [BestPairRead.model_validate(p) for p in pairs]


@tool(tags={ToolCategory.CORE.value, "memory"})
@map_domain_errors
async def update_reaction(
    entry_id: int,
    reaction: str,
    svc: TransitionHistoryService = Depends(get_transition_history_service),  # noqa: B008
) -> dict[str, str]:
    """Add user feedback (like/ban/skip/listened) to a transition."""
    await svc.update_reaction(entry_id, reaction)
    return {"status": "ok", "reaction": reaction}
