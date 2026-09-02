"""User override policy - applies user kwargs last (always wins)."""

from __future__ import annotations

from typing import Any

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class UserOverridePolicy(StemTransitionPolicy):
    """Apply user-provided kwargs last (always wins)."""

    name = "user_override"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        """Apply user overrides from track_input user_overrides dict."""
        user_overrides: dict[str, Any] = ctx.track_input.get("user_overrides", {})
        if not user_overrides:
            return plan

        updates: dict[str, Any] = {}
        if "hpf_hz" in user_overrides:
            updates["hpf_hz"] = user_overrides["hpf_hz"]
        if "gain_db" in user_overrides:
            updates["gain_db"] = user_overrides["gain_db"]
        if "fade_in_curve" in user_overrides:
            updates["fade_in_curve"] = user_overrides["fade_in_curve"]
        if "fade_out_curve" in user_overrides:
            updates["fade_out_curve"] = user_overrides["fade_out_curve"]
        if "fade_in_s" in user_overrides:
            updates["fade_in_s"] = user_overrides["fade_in_s"]
        if "fade_out_s" in user_overrides:
            updates["fade_out_s"] = user_overrides["fade_out_s"]

        if updates:
            updates["notes"] = (*plan.notes, "user_override_applied")
            return plan.update(**updates)
        return plan
