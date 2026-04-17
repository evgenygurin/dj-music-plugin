"""Handler for entity_create(entity="set_version", data={set_id, track_order, ...}).

Creates a DjSetVersion + DjSetItem rows + pairwise Transition rows for the
given ordering. Computes a summary quality score (mean of transition scores).
"""

from __future__ import annotations

import itertools
import json
from statistics import fmean
from typing import Any

from fastmcp.server.context import Context

from app.handlers.transition_persist import TransitionScorerProtocol
from app.repositories.unit_of_work import UnitOfWork
from app.shared.errors import NotFoundError, ValidationError


async def set_version_build_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    scorer: TransitionScorerProtocol,
) -> dict[str, Any]:
    set_id: int = int(data["set_id"])
    track_order: list[int] = [int(t) for t in data.get("track_order") or []]
    label: str = str(data.get("label") or "auto")
    gen_meta = data.get("generator_run_meta") or {}

    if not track_order:
        raise ValidationError("track_order must be non-empty")

    dj_set = await uow.sets.get(set_id)
    if dj_set is None:
        raise NotFoundError("set", set_id)

    features = await uow.track_features.get_scoring_features_batch(track_order)

    version = await uow.set_versions.create(
        set_id=set_id,
        label=label,
        generator_run_meta=json.dumps(gen_meta),
        quality_score=0.0,  # will update below
    )

    for idx, tid in enumerate(track_order):
        await uow.set_versions.add_item(
            version_id=version.id,
            track_id=tid,
            sort_index=idx,
        )

    transition_scores: list[float] = []
    for a, b in itertools.pairwise(track_order):
        if a not in features or b not in features:
            continue
        score = scorer.score(features[a], features[b])
        await uow.transitions.upsert(
            from_track_id=a,
            to_track_id=b,
            bpm_score=float(score.bpm),
            harmonic_score=float(score.harmonic),
            energy_score=float(score.energy),
            spectral_score=float(score.spectral),
            groove_score=float(score.groove),
            timbral_score=float(score.timbral),
            overall_quality=float(score.overall),
            hard_reject=bool(score.hard_reject),
            reject_reason=score.reject_reason,
        )
        transition_scores.append(float(score.overall))

    quality = fmean(transition_scores) if transition_scores else 0.0
    await uow.set_versions.update_quality(version.id, quality_score=quality)

    await ctx.info(
        f"built version {version.id}: {len(track_order)} items, "
        f"{len(transition_scores)} transitions, quality={quality:.3f}"
    )
    return {
        "version_id": version.id,
        "label": version.label,
        "item_count": len(track_order),
        "transition_count": len(transition_scores),
        "quality_score": quality,
    }
