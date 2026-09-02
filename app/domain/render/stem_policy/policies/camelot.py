"""Camelot policy — adjust HPF/vocal fade when keys clash."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


def _camelot_distance(a: int | None, b: int | None) -> int | None:
    if a is None or b is None:
        return None
    # Camelot wheel distance stub: 0-6, >5 = harsh
    # For now use simple circular distance on 0-23 pitch classes
    try:
        ai, bi = int(a) % 12, int(b) % 12
        d = abs(ai - bi)
        return min(d, 12 - d)
    except Exception:
        return None


class CamelotPolicy(StemTransitionPolicy):
    name = "camelot"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        ka = (ctx.track_features_in or {}).get("key_code")
        kb = (ctx.track_features_out or {}).get("key_code")
        dist = _camelot_distance(ka, kb)
        if dist is None or dist <= 5:
            return plan
        # harsh clash → bump HPF on harmonic/vocals a bit to thin mud
        if ctx.stem in ("harmonic", "vocals"):
            bumped = (plan.hpf_hz or 0) + 20
            bumped = min(250, max(80, bumped))
            return plan.update(
                hpf_hz=bumped, notes=(*plan.notes, f"camelot: dist={dist} hpf→{bumped}")
            )
        return plan.update(notes=(*plan.notes, f"camelot: dist={dist}"))
