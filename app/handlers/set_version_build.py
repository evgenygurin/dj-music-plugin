"""Handler for entity_create(entity="set_version", data={set_id, track_order, ...}).

Creates a DjSetVersion + DjSetItem rows for the given ordering. When every
track has scoring-level features available, scores pairwise transitions
and updates quality_score; otherwise persists the ordering as-is with
quality_score=0 so the set can be delivered before full analysis.
"""

from __future__ import annotations

import itertools
import json
from statistics import fmean
from typing import Any

from fastmcp.server.context import Context

from app.handlers._context_log import safe_info
from app.repositories.unit_of_work import UnitOfWork
from app.shared.errors import NotFoundError, ValidationError


async def set_version_build_handler(
    ctx: Context,
    uow: UnitOfWork,
    data: dict[str, Any],
    _registry: Any = None,  # unused — kept for entity_create signature parity
) -> dict[str, Any]:
    set_id: int = int(data["set_id"])
    track_order: list[int] = [int(t) for t in data.get("track_order") or []]
    # Accept ``version_label`` (canonical schema field) or ``label`` (alias).
    label: str = str(data.get("version_label") or data.get("label") or "auto")
    gen_meta = data.get("generator_run_meta") or {}

    if not track_order:
        raise ValidationError("track_order must be non-empty")

    dj_set = await uow.sets.get(set_id)
    if dj_set is None:
        raise NotFoundError("set", set_id)

    version = await uow.set_versions.create(
        set_id=set_id,
        label=label,
        generator_run_meta=json.dumps(gen_meta),
        quality_score=0.0,
    )
    item_count = await uow.set_versions.create_items(
        version_id=version.id, track_order=track_order
    )

    # Score pairwise transitions only when scorer + features are available.
    # Lazy import avoids the circular app.server → app.registry.defaults
    # → app.handlers.set_version_build loop at module-load time.
    transition_scores: list[float] = []
    try:
        from app.server.di import get_transition_scorer

        scorer = await get_transition_scorer(ctx)
    except RuntimeError:
        scorer = None

    if scorer is not None:
        # Lazy import — same circular-import dance as the scorer itself.
        from app.handlers.transition_persist import (
            _build_recipe_or_none,
            persist_transition_score,
        )

        features = await uow.track_features.get_scoring_features_batch(track_order)
        for a, b in itertools.pairwise(track_order):
            if a not in features or b not in features:
                continue
            feat_a = features[a]
            feat_b = features[b]
            score = scorer.score(feat_a, feat_b)
            transition_scores.append(float(score.overall))
            recipe = _build_recipe_or_none(score, feat_a, feat_b)
            # All-or-nothing intentional: if any upsert raises (FK race,
            # constraint violation), the surrounding UoW rolls back the
            # version + its items, leaving the DB consistent.
            await persist_transition_score(
                uow,
                from_track_id=a,
                to_track_id=b,
                score=score,
                recipe=recipe,
            )

    quality = fmean(transition_scores) if transition_scores else 0.0
    if transition_scores:
        version.quality_score = quality
        await uow.session.flush()

    await safe_info(
        ctx,
        f"built version {version.id}: {item_count} items, "
        f"{len(transition_scores)} transitions scored, quality={quality:.3f}",
    )
    return {
        "version_id": version.id,
        "label": version.label,
        "item_count": item_count,
        "transition_count": len(transition_scores),
        "quality_score": quality,
    }
