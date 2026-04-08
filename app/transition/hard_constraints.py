"""Hard-constraint gate for transition scoring.

Standalone function (no class state) — returns a zero-score
``TransitionScore`` with ``hard_reject=True`` if any constraint is
violated, otherwise ``None``. Hoisted out of ``scorer.py`` so the
component scorers in ``components/`` can be tested in isolation.

Thresholds come from ``app.config.settings.transition_hard_reject_*``;
they remain runtime-overridable for tests.
"""

from __future__ import annotations

from app.camelot.wheel import camelot_distance
from app.config import settings
from app.core.track_features import TrackFeatures
from app.transition.math_helpers import bpm_distance
from app.transition.score import TransitionScore


def check_hard_constraints(
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    pre_bpm_dist: float | None = None,
    pre_key_dist: int | None = None,
    pre_energy_delta: float | None = None,
) -> TransitionScore | None:
    """Return a zero-score rejection or ``None`` if all constraints pass.

    Pre-computed candidate distances bypass the recomputation done by
    ``CandidateService`` — pass them through when available.
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
        return TransitionScore(
            hard_reject=True,
            reject_reason=(
                f"BPM diff {bpm_diff:.1f} > {settings.transition_hard_reject_bpm_diff}"
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
        return TransitionScore(
            hard_reject=True,
            reject_reason=(
                f"Camelot distance {key_dist} >= {settings.transition_hard_reject_camelot_dist}"
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
        return TransitionScore(
            hard_reject=True,
            reject_reason=(
                f"Energy gap {energy_gap:.1f} LUFS > {settings.transition_hard_reject_energy_gap}"
            ),
        )

    return None
