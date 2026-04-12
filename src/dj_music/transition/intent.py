"""Context-aware transition intent and weight modifiers."""

from __future__ import annotations

from enum import StrEnum

from dj_music.core.constants import SetTemplate


class TransitionIntent(StrEnum):
    MAINTAIN = "maintain"
    RAMP_UP = "ramp_up"
    COOL_DOWN = "cool_down"
    CONTRAST = "contrast"


INTENT_WEIGHT_MODIFIERS: dict[TransitionIntent, dict[str, float]] = {
    TransitionIntent.MAINTAIN: {
        "bpm": 0.28,
        "harmonic": 0.18,
        "energy": 0.15,
        "spectral": 0.15,
        "groove": 0.14,
        "timbral": 0.10,
    },
    TransitionIntent.RAMP_UP: {
        "bpm": 0.20,
        "harmonic": 0.25,
        "energy": 0.30,
        "spectral": 0.10,
        "groove": 0.05,
        "timbral": 0.10,
    },
    TransitionIntent.COOL_DOWN: {
        "bpm": 0.20,
        "harmonic": 0.20,
        "energy": 0.25,
        "spectral": 0.15,
        "groove": 0.05,
        "timbral": 0.15,
    },
    TransitionIntent.CONTRAST: {
        "bpm": 0.15,
        "harmonic": 0.12,
        "energy": 0.18,
        "spectral": 0.20,
        "groove": 0.15,
        "timbral": 0.20,
    },
}


# (warmup_end, peak_start, peak_end) — fractions of the set duration.
# Different templates have wildly different energy arcs: a warm_up_30
# is mostly warm-up, a peak_hour_60 is mostly peak, a closing_60 is
# mostly cool-down. The fallback row keeps the historical 0.20/0.50/0.85
# defaults for backward compatibility when no template is supplied.
_TEMPLATE_PHASE_TABLE: dict[SetTemplate, tuple[float, float, float]] = {
    SetTemplate.WARM_UP_30: (0.50, 0.70, 0.85),
    SetTemplate.CLASSIC_60: (0.20, 0.50, 0.80),
    SetTemplate.PEAK_HOUR_60: (0.10, 0.30, 0.90),
    SetTemplate.ROLLER_90: (0.15, 0.40, 0.85),
    SetTemplate.PROGRESSIVE_120: (0.30, 0.60, 0.85),
    SetTemplate.WAVE_120: (0.20, 0.50, 0.80),
    SetTemplate.CLOSING_60: (0.05, 0.15, 0.50),
    SetTemplate.FULL_LIBRARY: (0.20, 0.50, 0.85),
}
_DEFAULT_PHASE = (0.20, 0.50, 0.85)


def infer_intent(
    set_position: float,
    energy_delta_lufs: float,
    template: SetTemplate | None = None,
) -> TransitionIntent:
    """Auto-detect transition intent from set position and energy delta.

    When ``template`` is supplied, the warmup/peak phase boundaries are
    pulled from a per-template table — a peak-hour set treats position
    0.15 as already-peak, while a closing set treats it as already
    cooling. With ``template=None`` the historical 0.20/0.85 cutoffs
    are used, so existing call sites are unaffected.
    """
    warmup_end, _peak_start, peak_end = (
        _TEMPLATE_PHASE_TABLE[template] if template is not None else _DEFAULT_PHASE
    )

    if set_position < warmup_end:
        return TransitionIntent.RAMP_UP
    if set_position > peak_end:
        return TransitionIntent.COOL_DOWN
    if energy_delta_lufs > 2.0:
        return TransitionIntent.RAMP_UP
    if energy_delta_lufs < -2.0:
        return TransitionIntent.COOL_DOWN
    return TransitionIntent.MAINTAIN
