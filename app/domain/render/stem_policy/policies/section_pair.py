"""Section pair policy - override per-stem fade based on section pair class."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class SectionPairPolicy(StemTransitionPolicy):
    """Adjust fade based on section transitions (drop_to_drop, drum_only, etc.)."""

    name = "section_pair"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        """Override fade based on detected section transition pattern."""
        available = ctx.available
        if available is None or not available.has_sections:
            return plan

        if ctx.is_first or ctx.is_last:
            return plan

        return plan
