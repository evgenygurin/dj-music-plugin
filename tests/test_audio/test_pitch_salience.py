"""Tests for PitchSalienceAnalyzer."""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050
DURATION = 3.0


def _make_signal(samples: np.ndarray) -> AudioSignal:
    return AudioSignal(
        samples=samples.astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=len(samples) / SAMPLE_RATE,
    )


def _harmonic_signal() -> np.ndarray:
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), endpoint=False)
    return (
        0.4 * np.sin(2 * np.pi * 440 * t)
        + 0.2 * np.sin(2 * np.pi * 880 * t)
        + 0.1 * np.sin(2 * np.pi * 1320 * t)
        + 0.05 * np.sin(2 * np.pi * 1760 * t)
    ).astype(np.float32)


def _noise_signal() -> np.ndarray:
    rng = np.random.default_rng(42)
    return (0.3 * rng.standard_normal(int(SAMPLE_RATE * DURATION))).astype(np.float32)


def test_pitch_salience_happy_path():
    pytest.importorskip("essentia", reason="essentia not installed")
    from app.audio.analyzers.pitch_salience import PitchSalienceAnalyzer

    signal = _make_signal(_harmonic_signal())
    analyzer = PitchSalienceAnalyzer()
    result = analyzer.run(AnalysisContext(signal))

    assert result.success
    assert "pitch_salience_mean" in result.features
    val = result.features["pitch_salience_mean"]
    assert isinstance(val, float)
    assert 0.0 <= val <= 1.0


def test_pitch_salience_harmonic_higher_than_noise():
    pytest.importorskip("essentia", reason="essentia not installed")
    from app.audio.analyzers.pitch_salience import PitchSalienceAnalyzer

    analyzer = PitchSalienceAnalyzer()
    harmonic = analyzer.run(AnalysisContext(_make_signal(_harmonic_signal())))
    noise = analyzer.run(AnalysisContext(_make_signal(_noise_signal())))

    if harmonic.success and noise.success:
        assert harmonic.features["pitch_salience_mean"] > noise.features["pitch_salience_mean"]


def test_pitch_salience_graceful_skip_no_essentia():
    from unittest.mock import patch

    with patch.dict("sys.modules", {"essentia": None, "essentia.standard": None}):
        from app.audio.analyzers.pitch_salience import PitchSalienceAnalyzer

        analyzer = PitchSalienceAnalyzer()
        assert not analyzer.is_available()
