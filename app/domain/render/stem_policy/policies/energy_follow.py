"""Energy follow policy — per-stem energy matching (L2 + optional L6)."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class EnergyFollowPolicy(StemTransitionPolicy):
    """Adjust gain_db by per-stem energy_mean delta when available."""

    name = "energy_follow"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        available = ctx.available
        if available is None or not available.has_stem_features:
            # graceful fallback: no per-stem data → no change
            return plan
        e_in = (ctx.stem_features_in or {}).get("energy_mean")
        e_out = (ctx.stem_features_out or {}).get("energy_mean")
        if e_in is None or e_out is None:
            return plan
        delta = float(e_out) - float(e_in)
        # small trim proportional to delta, clamped to ±1.5 dB
        trim = max(-1.5, min(1.5, delta * 2.0))
        if abs(trim) < 0.05:
            return plan
        return plan.update(
            gain_db=plan.gain_db + trim,
            notes=(*plan.notes, f"energy_follow: {ctx.stem} trim={trim:+.2f}dB"),
        )
