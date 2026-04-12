"""Tests for rhythm helper functions."""

from __future__ import annotations

import numpy as np

from dj_music.audio.core.context import AnalysisContext
from dj_music.audio.core.rhythm import (
    find_beat_times,
    sample_interpolated,
    spectral_flux_onset_envelope,
    tempo_from_onset_autocorrelation,
)
from dj_music.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
HOP_LENGTH = 512


def _click_signal(bpm: float, duration_s: float = 8.0) -> AudioSignal:
    n_samples = int(SAMPLE_RATE * duration_s)
    samples = np.zeros(n_samples, dtype=np.float32)
    interval = 60.0 / bpm
    kick_len = int(0.01 * SAMPLE_RATE)
    for beat_time in np.arange(0.0, duration_s, interval):
        start = round(beat_time * SAMPLE_RATE)
        end = min(start + kick_len, n_samples)
        if end > start:
            samples[start:end] = 1.0
    return AudioSignal(samples=samples, sample_rate=SAMPLE_RATE, duration_seconds=duration_s)


def test_spectral_flux_onset_envelope_is_normalized() -> None:
    ctx = AnalysisContext(_click_signal(128.0))
    onset_env = spectral_flux_onset_envelope(ctx.magnitude, ctx.frame_energies)

    assert onset_env.shape == ctx.frame_energies.shape
    assert float(np.min(onset_env)) >= 0.0
    assert float(np.max(onset_env)) == 1.0


def test_tempo_from_onset_autocorrelation_recovers_click_track_bpm() -> None:
    ctx = AnalysisContext(_click_signal(132.0))
    onset_env = ctx.get_onset_env()

    estimate = tempo_from_onset_autocorrelation(onset_env, SAMPLE_RATE, HOP_LENGTH)

    assert abs(estimate.bpm - 132.0) < 1.0
    assert estimate.confidence > 0.1
    assert estimate.lag_frames > 0


def test_find_beat_times_tracks_periodic_peaks() -> None:
    ctx = AnalysisContext(_click_signal(130.0))
    onset_env = ctx.get_onset_env()
    estimate = tempo_from_onset_autocorrelation(onset_env, SAMPLE_RATE, HOP_LENGTH)

    beat_times = find_beat_times(onset_env, SAMPLE_RATE, HOP_LENGTH, bpm_hint=estimate.bpm)

    assert len(beat_times) >= 10
    intervals = np.diff(beat_times[:8])
    expected = 60.0 / 130.0
    assert float(np.mean(np.abs(intervals - expected))) < 0.05


def test_sample_interpolated_uses_linear_interpolation() -> None:
    values = np.array([0.0, 10.0, 20.0], dtype=np.float64)

    assert sample_interpolated(values, 0.5) == 5.0
    assert sample_interpolated(values, 1.25) == 12.5
    assert sample_interpolated(values, -1.0) == 0.0
