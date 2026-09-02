"""Cross-similarity policy — tighten blend when DTW score is high."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class CrossSimilarityPolicy(StemTransitionPolicy):
    name = "cross_similarity"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        available = ctx.available
        if available is None or not available.has_cross_similarity:
            return plan
        score = (
            (ctx.track_input.get("cross_similarity") or ctx.track_input.get("best_match_score"))
            if isinstance(ctx.track_input, dict)
            else None
        )
        if score is None and isinstance(ctx.track_input, dict):
            cs = ctx.track_input.get("cross_similarity")
            if isinstance(cs, dict):
                score = cs.get("best_match_score")
        if score is None:
            return plan
        try:
            if float(score) <= 0.90:
                return plan
        except Exception:
            return plan
        # high similarity → tighten (shorter) to avoid mud
        new_in = plan.fade_in_s * 0.85 if plan.fade_in_s is not None else None
        new_out = plan.fade_out_s * 0.85 if plan.fade_out_s is not None else None
        return plan.update(
            fade_in_s=new_in,
            fade_out_s=new_out,
            notes=(*plan.notes, f"cross_similarity: score={float(score):.2f}"),
        )
