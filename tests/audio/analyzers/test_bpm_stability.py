"""Regression tests for BPMDetector tempo stability / variable_tempo.

Covers the median-IBI-filter fix: coefficient of variation of
inter-beat intervals must reject seam-artifact and missed-beat
outliers before deciding `variable_tempo` / `bpm_stability`.

Background — stitched-clip pipeline feeds BPMDetector a concatenation
of 3 x 20 s windows from different points in the source track. Phase
discontinuities at window boundaries produce 2-4 spurious IBIs per
track (either ~0 or ~2x median). Likewise `find_beat_times` can miss
beats in quiet breakdown sections. Without outlier rejection, 5 %
spurious IBIs are enough to drive CV > 0.15 and false-flag the track
as variable-tempo, killing the transition BPM score via
`scoring_variable_tempo_penalty`.

Tests drive the extracted `compute_tempo_stability(beat_times)` helper
so we can hit the decision logic directly without routing through
librosa + audio fixtures.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.analyzers.bpm import compute_tempo_stability


def _beat_times_from_ibis(ibis: list[float]) -> np.ndarray:
    """Convert a sequence of inter-beat intervals to monotonic beat times."""
    return np.concatenate([[0.0], np.cumsum(ibis)])


def test_steady_techno_scores_high_stability() -> None:
    """50 identical IBIs at 128 BPM → stability ≈ 1.0, variable=False."""
    ibis = [60.0 / 128.0] * 50
    stability, variable_tempo = compute_tempo_stability(_beat_times_from_ibis(ibis))
    assert stability == pytest.approx(1.0, abs=0.01)
    assert variable_tempo is False


def test_seam_outlier_ibis_do_not_flag_variable_tempo() -> None:
    """50 steady IBIs + 3 outlier IBIs (2x median, simulating seam
    discontinuities or missed beats) must NOT flag variable_tempo.

    This is the core regression fix — without the median filter,
    3 doubled IBIs push CV above 0.15 and lose the track.
    """
    steady = 60.0 / 128.0  # 0.46875 s
    ibis = [steady] * 50 + [steady * 2, steady * 2, steady * 2]
    stability, variable_tempo = compute_tempo_stability(_beat_times_from_ibis(ibis))
    assert variable_tempo is False, "3 spurious 2x IBIs out of 53 must not flag variable tempo"
    assert stability > 0.9, f"stability={stability:.3f} — outliers leaked into CV"


def test_extra_beat_outliers_do_not_flag_variable_tempo() -> None:
    """Symmetric case: spurious doubled-detection IBIs (0.5x median)."""
    steady = 60.0 / 128.0
    ibis = [steady] * 50 + [steady * 0.5, steady * 0.5]
    _, variable_tempo = compute_tempo_stability(_beat_times_from_ibis(ibis))
    assert variable_tempo is False


def test_real_variable_tempo_still_detected() -> None:
    """A real 25 % tempo drift must still fire variable_tempo.

    Outlier filter keeps ±50 % of median, so a genuine ~25 % drift
    stays entirely within the kept region and drives CV through the
    0.15 threshold. This confirms the filter does not mask actual
    tempo variability — it only drops obvious doubled / halved IBIs.
    """
    rng = np.random.default_rng(seed=42)
    median_ibi = 60.0 / 128.0
    ibis = median_ibi + rng.normal(0, 0.25 * median_ibi, size=50)
    _, variable_tempo = compute_tempo_stability(_beat_times_from_ibis(ibis.tolist()))
    assert variable_tempo is True, "genuine ~25 % tempo drift must flag variable (CV > 0.15)"


def test_empty_beats_returns_neutral() -> None:
    """Degenerate input (<3 beats) → stability=0, variable=False (documented)."""
    stability, variable_tempo = compute_tempo_stability(np.array([0.0, 0.469]))
    assert stability == 0.0
    assert variable_tempo is False
