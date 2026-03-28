"""Context-aware transition intent and weight modifiers."""

from __future__ import annotations

from enum import StrEnum


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


def infer_intent(
    set_position: float,
    energy_delta_lufs: float,
) -> TransitionIntent:
    """Auto-detect transition intent from set position and energy delta."""
    if set_position < 0.2:
        return TransitionIntent.RAMP_UP
    if set_position > 0.85:
        return TransitionIntent.COOL_DOWN
    if energy_delta_lufs > 2.0:
        return TransitionIntent.RAMP_UP
    if energy_delta_lufs < -2.0:
        return TransitionIntent.COOL_DOWN
    return TransitionIntent.MAINTAIN
