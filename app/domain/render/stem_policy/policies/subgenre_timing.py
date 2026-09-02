"""Subgenre timing policy — scale transition lengths per subgenre."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)

# Multipliers per subgenre (design §5 SubgenreTimingPolicy). Keep table small,
# values are relative to base_d_in/out. Unknown subgenre → 1.0.
_SUBGENRE_MULT: dict[str, float] = {
    "hypnotic_techno": 1.15,
    "dub_techno": 1.30,
    "hard_techno": 0.85,
    "peak_time_techno": 0.90,
    "driving_techno": 1.00,
    "industrial_techno": 0.85,
    "acid_techno": 1.00,
    "deep_house": 1.10,
    "tech_house": 0.95,
    "progressive_house": 1.20,
    "classic_house": 1.00,
}


class SubgenreTimingPolicy(StemTransitionPolicy):
    name = "subgenre_timing"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        subgenre = (
            (ctx.track_input.get("subgenre") or "").lower()
            if isinstance(ctx.track_input, dict)
            else ""
        )
        mult = _SUBGENRE_MULT.get(subgenre)
        if mult is None or mult == 1.0:
            return plan
        # scale fades, pinpoint stays absolute (beats)
        new_in = plan.fade_in_s * mult if plan.fade_in_s is not None else None
        new_out = plan.fade_out_s * mult if plan.fade_out_s is not None else None
        if new_in == plan.fade_in_s and new_out == plan.fade_out_s:
            return plan
        return plan.update(
            fade_in_s=new_in,
            fade_out_s=new_out,
            notes=(*plan.notes, f"subgenre_timing: {subgenre} x{mult:.2f}"),
        )
