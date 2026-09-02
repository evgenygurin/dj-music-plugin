"""Beatgrid policy - prefer DjBeatgrid.bpm over stored bpm for time-stretch."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class BeatgridPolicy(StemTransitionPolicy):
    """Record note about using measured BPM from beatgrid if available."""

    name = "beatgrid"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        """Add note if measured BPM is available."""
        available = ctx.available
        if available is None or not available.has_beatgrid:
            return plan

        bpm_in = ctx.track_features_in.get("bpm_measured") if ctx.track_features_in else None
        bpm_out = ctx.track_features_out.get("bpm_measured") if ctx.track_features_out else None
        if bpm_in is None and bpm_out is None:
            return plan

        bpm = bpm_in or bpm_out
        if bpm is None or bpm == 0:
            return plan
        drift = abs(bpm - ctx.target_bpm)
        if drift > 1.0:
            return plan.update(
                notes=(*plan.notes, f"beatgrid: bpm_drift={drift:.2f}"),
            )
        return plan
