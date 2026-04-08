"""Background task implementations for long-running operations.

These functions are designed to be scheduled via Docket in background workers.
"""

from __future__ import annotations

from typing import Any

from docket import Progress as DocketProgress
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.track_features import TrackFeatures
from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.track import Track
from app.domain.transition import TransitionScorer


async def score_track_transitions(
    track_id: int,
    session: AsyncSession,
    progress: DocketProgress | None = None,
) -> dict[str, Any]:
    """Score all valid transitions for a track against library.

    Called when:
    - Track features are updated
    - New track with features is imported
    - Manual trigger via tool

    Returns summary of scored transitions.
    """
    if progress:
        await progress.set_message(f"Loading features for track {track_id}...")

    # Load track features
    stmt = (
        select(Track, TrackAudioFeaturesComputed)
        .join(TrackAudioFeaturesComputed, Track.id == TrackAudioFeaturesComputed.track_id)
        .where(Track.id == track_id)
    )
    result = await session.execute(stmt)
    row = result.first()

    if row is None:
        return {"error": f"Track {track_id} not found or has no features", "scored": 0}

    track, features = row
    from_features = TrackFeatures.from_db(features)

    # Get all other tracks with features
    stmt = (
        select(Track, TrackAudioFeaturesComputed)
        .join(TrackAudioFeaturesComputed, Track.id == TrackAudioFeaturesComputed.track_id)
        .where(Track.id != track_id, Track.status == 0)  # active only
    )
    result = await session.execute(stmt)
    candidates = result.all()

    total_candidates = len(candidates)
    if progress:
        await progress.set_total(total_candidates)
        await progress.set_message(f"Scoring {total_candidates} transitions...")

    scorer = TransitionScorer()
    scored_count = 0
    hard_rejects = 0

    for idx, (_candidate_track, candidate_features) in enumerate(candidates):
        to_features = TrackFeatures.from_db(candidate_features)
        score = scorer.score(from_features, to_features)

        # In real implementation: persist to transitions table
        # await session.execute(
        #     insert(Transition).values(
        #         from_track_id=track_id,
        #         to_track_id=candidate_track.id,
        #         bpm_score=score.bpm,
        #         ...
        #     )
        #     .on_conflict_do_update(...)
        # )

        scored_count += 1
        if score.hard_reject:
            hard_rejects += 1

        if progress and idx % 50 == 0:
            await progress.set_message(
                f"Scored {scored_count} / {total_candidates} transitions..."
            )
            await progress.increment(50)

    if progress:
        await progress.set_message(
            f"Complete: {scored_count} transitions, {hard_rejects} hard rejects"
        )

    return {
        "track_id": track_id,
        "track_title": track.title,
        "total_candidates": total_candidates,
        "scored": scored_count,
        "hard_rejects": hard_rejects,
    }
