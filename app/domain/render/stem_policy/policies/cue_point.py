"""Cue point policy — snap mix-in/out to downbeat/drop cues."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class CuePointPolicy(StemTransitionPolicy):
    name = "cue_point"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        available = ctx.available
        if available is None or not available.has_cue_points:
            return plan
        # Graceful: if cue data present, just annotate (real snap is done by phrase_align)
        cue_in = (ctx.track_features_in or {}).get("first_downbeat_ms")
        cue_out = (ctx.track_features_out or {}).get("first_downbeat_ms")
        if cue_in is None and cue_out is None:
            return plan
        return plan.update(notes=(*plan.notes, "cue_point: snap to cue"))
