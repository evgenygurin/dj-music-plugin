"""Feedback policy — hard-skip banned outgoing, warn on archived."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class FeedbackPolicy(StemTransitionPolicy):
    name = "feedback"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        available = ctx.available
        if available is None or not available.has_user_feedback:
            return plan
        fb_out = (
            (ctx.track_features_out or {}).get("feedback")
            if isinstance(ctx.track_features_out, dict)
            else None
        )
        fb_in = (
            (ctx.track_features_in or {}).get("feedback")
            if isinstance(ctx.track_features_in, dict)
            else None
        )
        fb = fb_out or fb_in
        if not isinstance(fb, dict):
            # also check track_input
            fb = (
                (ctx.track_input.get("feedback_out") or ctx.track_input.get("feedback_in"))
                if isinstance(ctx.track_input, dict)
                else None
            )
        if not isinstance(fb, dict):
            return plan
        status = fb.get("status") or fb.get("feedback_type")
        if status == "banned":
            # hard-skip: zero-length outgoing
            return plan.update(
                fade_out_s=0.05, notes=(*plan.notes, "feedback: banned → hard-skip")
            )
        if status == "archived":
            return plan.update(notes=(*plan.notes, "feedback: archived"))
        return plan
