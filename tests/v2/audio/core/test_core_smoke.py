"""Smoke tests for v2 audio core primitives (Task 10 port parity).

Verifies the ported core package is importable and the fundamental DSP
primitives produce sensible outputs on synthetic signals. Heavier
behavior is covered by the legacy tests in ``tests/test_audio``.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.v2.audio.core import (
    AnalysisContext,
    AnalyzerResult,
    AudioSignal,
    FrameParams,
    compute_energy_slope,
    compute_frame_energies,
)
from app.v2.audio.core.rhythm import (
    onset_autocorrelation,
    spectral_flux_onset_envelope,
    tempo_from_onset_autocorrelation,
)
from app.v2.audio.core.spectral import (
    band_energies,
    compute_stft,
    spectral_centroid,
    spectral_flatness,
    spectral_rolloff,
)
from app.v2.audio.core.tonal import (
    compute_pitch_class_chroma,
    mel_filterbank,
    tonal_centroid,
)

SR = 22050


def _sine(freq: float, sec: float = 1.0) -> np.ndarray:
    t = np.linspace(0, sec, int(SR * sec), endpoint=False, dtype=np.float32)
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def test_types_construct() -> None:
    sig = AudioSignal(samples=_sine(440), sample_rate=SR, duration_seconds=1.0)
    assert sig.sample_rate == SR
    res = AnalyzerResult(analyzer_name="x", features={"a": 1})
    assert res.success is True
    fp = FrameParams()
    assert fp.frame_length == 2048 and fp.hop_length == 512


def test_frame_energies_and_slope() -> None:
    s = _sine(440, sec=1.0)
    en = compute_frame_energies(s)
    assert en.max() <= 1.0 + 1e-9
    assert en.min() >= 0.0
    assert compute_energy_slope(np.arange(10, dtype=np.float64)) > 0


def test_stft_and_spectral() -> None:
    s = _sine(1000, sec=0.5)
    stft = compute_stft(s)
    mag = np.abs(stft)
    freqs = np.fft.rfftfreq(2048, d=1.0 / SR)
    c = spectral_centroid(mag, freqs)
    assert 500 < c < 2500
    r = spectral_rolloff(mag, freqs, 0.85)
    assert r > 100
    f = spectral_flatness(mag)
    assert 0.0 <= f <= 1.0
    be = band_energies(mag, freqs, {"low": (0, 500), "mid": (500, 2000), "high": (2000, SR / 2)})
    assert pytest.approx(sum(be.values()), abs=1e-6) == sum(be.values())


def test_context_shared_state() -> None:
    sig = AudioSignal(samples=_sine(440, 0.5), sample_rate=SR, duration_seconds=0.5)
    ctx = AnalysisContext(sig)
    assert ctx.stft.shape[0] == 1025  # 2048 // 2 + 1
    assert ctx.magnitude.shape == ctx.stft.shape
    assert ctx.freqs.shape[0] == 1025
    assert ctx.frame_energies.ndim == 1
    assert ctx.sr == SR


def test_onset_and_tempo() -> None:
    # Click track at 120 BPM (2 Hz) for a few seconds
    sec = 4.0
    n = int(SR * sec)
    sig = np.zeros(n, dtype=np.float32)
    for beat in range(int(sec * 2)):
        idx = int(beat * SR / 2)
        if idx + 100 < n:
            sig[idx : idx + 100] = 1.0
    stft = compute_stft(sig)
    env = spectral_flux_onset_envelope(np.abs(stft))
    assert env.max() > 0
    ac = onset_autocorrelation(env)
    assert ac.shape[0] == env.shape[0]
    est = tempo_from_onset_autocorrelation(env, SR, hop_length=512, min_bpm=60, max_bpm=200)
    assert 100 < est.bpm < 140


def test_tonal() -> None:
    s = _sine(440, 0.5)
    stft = compute_stft(s)
    mag = np.abs(stft)
    freqs = np.fft.rfftfreq(2048, d=1.0 / SR)
    chroma = compute_pitch_class_chroma(mag, freqs)
    assert chroma.shape[0] == 12
    cv = np.ones(12) / 12.0
    tc = tonal_centroid(cv)
    assert tc.shape == (6,)
    fb = mel_filterbank(freqs, SR, n_mels=40)
    assert fb.shape == (40, len(freqs))


def test_loader_importable() -> None:
    # Actual file loading requires real audio fixtures — smoke only.
    from app.v2.audio.core.loader import AudioLoader

    loader = AudioLoader(target_sr=SR)
    assert loader._target_sr == SR
