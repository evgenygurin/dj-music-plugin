"""Hard-constraint gate for transition scoring.

Standalone function (no class state) — returns a ``ConstraintResult``
with hard rejection (if any) and soft conflict flags (vocal/drum).

Thresholds come from ``app.config.settings.transition_hard_reject_*``;
they remain runtime-overridable for tests.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.camelot.wheel import camelot_distance
from app.config import settings
from app.entities.audio.features import TrackFeatures
from app.transition.constants import (
    GROOVE_CONFLICT_THRESHOLD,
    VOCAL_PITCH_SALIENCE_THRESHOLD,
    VOCAL_SPECTRAL_CENTROID_FLOOR_HZ,
)
from app.transition.math_helpers import bpm_distance
from app.transition.score import TransitionScore


@dataclass(frozen=True)
class ConstraintResult:
    """Result of hard-constraint + soft-conflict checks."""

    rejection: TransitionScore | None = None  # non-None → hard reject
    vocal_conflict: bool = False  # both tracks have vocals → mute outgoing
    drum_conflict: bool = False  # drum patterns dissimilar → mute incoming drums


def check_hard_constraints(
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    pre_bpm_dist: float | None = None,
    pre_key_dist: int | None = None,
    pre_energy_delta: float | None = None,
) -> ConstraintResult:
    """Check hard constraints and detect soft conflicts.

    Returns ``ConstraintResult`` with:
    - ``rejection``: non-None TransitionScore if hard-rejected
    - ``vocal_conflict``: True if both tracks have vocals (mute outgoing)
    - ``drum_conflict``: True if drum patterns are dissimilar (mute incoming)
    """
    # ── BPM constraint ──
    bpm_diff: float | None
    if pre_bpm_dist is not None:
        bpm_diff = pre_bpm_dist
    elif from_t.bpm is not None and to_t.bpm is not None:
        bpm_diff = bpm_distance(from_t.bpm, to_t.bpm)
    else:
        bpm_diff = None

    if bpm_diff is not None and bpm_diff > settings.transition_hard_reject_bpm_diff:
        return ConstraintResult(
            rejection=TransitionScore(
                hard_reject=True,
                reject_reason=(
                    f"BPM diff {bpm_diff:.1f} > {settings.transition_hard_reject_bpm_diff}"
                ),
            ),
        )

    # ── Key constraint ──
    key_dist: int | None
    if pre_key_dist is not None:
        key_dist = pre_key_dist
    elif from_t.key_code is not None and to_t.key_code is not None:
        key_dist = camelot_distance(from_t.key_code, to_t.key_code)
    else:
        key_dist = None

    if key_dist is not None and key_dist >= settings.transition_hard_reject_camelot_dist:
        return ConstraintResult(
            rejection=TransitionScore(
                hard_reject=True,
                reject_reason=(
                    f"Camelot distance {key_dist} >= {settings.transition_hard_reject_camelot_dist}"
                ),
            ),
        )

    # ── Energy constraint ──
    energy_gap: float | None
    if pre_energy_delta is not None:
        energy_gap = pre_energy_delta
    elif from_t.integrated_lufs is not None and to_t.integrated_lufs is not None:
        energy_gap = abs(from_t.integrated_lufs - to_t.integrated_lufs)
    else:
        energy_gap = None

    if energy_gap is not None and energy_gap > settings.transition_hard_reject_energy_gap:
        return ConstraintResult(
            rejection=TransitionScore(
                hard_reject=True,
                reject_reason=(
                    f"Energy gap {energy_gap:.1f} LUFS > {settings.transition_hard_reject_energy_gap}"
                ),
            ),
        )

    # ── Soft conflict: vocal overlap (Mosaikbox 2024) ──
    # Both tracks have strong vocal/melodic content → outgoing vocals
    # should be muted during the transition to prevent clash.
    vocal_conflict = (
        from_t.pitch_salience_mean is not None
        and to_t.pitch_salience_mean is not None
        and from_t.pitch_salience_mean > VOCAL_PITCH_SALIENCE_THRESHOLD
        and to_t.pitch_salience_mean > VOCAL_PITCH_SALIENCE_THRESHOLD
        and (from_t.spectral_centroid_hz or 0) > VOCAL_SPECTRAL_CENTROID_FLOOR_HZ
        and (to_t.spectral_centroid_hz or 0) > VOCAL_SPECTRAL_CENTROID_FLOOR_HZ
    )

    # ── Soft conflict: drum pattern mismatch (Mosaikbox 2024) ──
    # Dissimilar drum patterns cause comb filtering → incoming drums
    # should be attenuated during the overlap.
    drum_conflict = False
    if (
        from_t.onset_rate is not None
        and to_t.onset_rate is not None
        and from_t.kick_prominence is not None
        and to_t.kick_prominence is not None
    ):
        onset_sim = 1.0 - min(abs(from_t.onset_rate - to_t.onset_rate) / 5.0, 1.0)
        kick_sim = 1.0 - min(abs(from_t.kick_prominence - to_t.kick_prominence) / 0.5, 1.0)
        drum_sim = 0.5 * onset_sim + 0.5 * kick_sim
        drum_conflict = drum_sim < GROOVE_CONFLICT_THRESHOLD

    return ConstraintResult(
        vocal_conflict=vocal_conflict,
        drum_conflict=drum_conflict,
    )
