"""Base timbre policy - sets HPF and gain from STEM_TIMBRE defaults."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class BaseTimbrePolicy(StemTransitionPolicy):
    """Set HPF and gain from STEM_TIMBRE defaults."""

    name = "base_timbre"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        """Apply stem timbre settings."""
        from app.domain.render.stem_timbre import stem_timbre

        timbre = stem_timbre(ctx.stem)
        return plan.update(
            hpf_hz=timbre.hpf_hz,
            gain_db=timbre.gain_db,
            notes=(*plan.notes, f"base_timbre: hpf={timbre.hpf_hz}hz gain={timbre.gain_db}db"),
        )
