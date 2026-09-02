"""Embedding policy — lengthen blend when tracks are too similar."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class EmbeddingPolicy(StemTransitionPolicy):
    name = "embedding"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        available = ctx.available
        if available is None or not available.has_embedding:
            return plan
        sim = (
            (
                ctx.track_input.get("embedding_cosine")
                or ctx.track_input.get("embedding_similarity")
            )
            if isinstance(ctx.track_input, dict)
            else None
        )
        if sim is None:
            return plan
        try:
            if float(sim) <= 0.85:
                return plan
        except Exception:
            return plan
        new_in = plan.fade_in_s * 1.30 if plan.fade_in_s is not None else None
        new_out = plan.fade_out_s * 1.30 if plan.fade_out_s is not None else None
        return plan.update(
            fade_in_s=new_in,
            fade_out_s=new_out,
            notes=(*plan.notes, f"embedding: sim={float(sim):.2f}"),
        )
