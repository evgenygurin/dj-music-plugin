"""Stem role policy — canonical per-stem base fades (always)."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class StemRolePolicy(StemTransitionPolicy):
    """Assign base curve/phase per stem role (design §3.7 #6)."""

    name = "stem_role"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        if ctx.is_first or ctx.is_last:
            return plan
        # drums continuous: full d_in/out; others staggered via p1/p2 by filtergraph.
        # Here we only tag notes + pick curves; actual durations are set by BarPlanner.
        role_curve = {
            "drums": "qsin",
            "bass": "qsin",
            "percussion": "tri",
            "harmonic": "qsin",
            "vocals": "tri",
        }.get(ctx.stem, "qsin")
        if plan.fade_in_curve == role_curve and plan.fade_out_curve == role_curve:
            return plan
        return plan.update(
            fade_in_curve=role_curve,
            fade_out_curve=role_curve,
            notes=(*plan.notes, f"stem_role: {ctx.stem} curve={role_curve}"),
        )
