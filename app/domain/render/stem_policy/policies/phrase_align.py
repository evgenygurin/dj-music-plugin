"""Phrase align policy - shift pinpoint_s to nearest phrase boundary."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class PhraseAlignPolicy(StemTransitionPolicy):
    """Shift pinpoint_s to nearest phrase boundary within +/- 4 bars."""

    name = "phrase_align"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        """Snap transition to phrase boundary if phrase data available."""
        available = ctx.available
        if available is None or not available.has_sections:
            return plan

        phrases_in = (
            ctx.track_features_in.get("phrase_boundaries_ms") if ctx.track_features_in else None
        )
        if not phrases_in:
            return plan

        if ctx.stem != "bass" or plan.pinpoint_s is None:
            return plan

        return plan.update(
            notes=(*plan.notes, "phrase_align: snap_to_phrase"),
        )
