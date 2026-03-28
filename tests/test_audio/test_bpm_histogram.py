"""Tests for BpmHistogramAnalyzer."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from app.audio.core.context import AnalysisContext
from app.audio.core.types import AudioSignal

SAMPLE_RATE = 22050


def _make_signal(n_samples: int = 22050 * 3) -> AudioSignal:
    rng = np.random.default_rng(42)
    samples = rng.standard_normal(n_samples).astype(np.float32) * 0.1
    return AudioSignal(
        samples=samples,
        sample_rate=SAMPLE_RATE,
        duration_seconds=n_samples / SAMPLE_RATE,
    )


def test_bpm_histogram_with_stable_intervals():
    pytest.importorskip("essentia", reason="essentia not installed")
    from app.audio.analyzers.bpm_histogram import BpmHistogramAnalyzer

    analyzer = BpmHistogramAnalyzer()
    ctx = AnalysisContext(_make_signal())
    interval = 60.0 / 130.0
    prior: dict[str, Any] = {
        "beats_intervals": [interval] * 50,
        "beat_times": [i * interval for i in range(51)],
    }
    result = analyzer.run(ctx, prior)

    assert result.success
    assert "bpm_histogram_first_peak_weight" in result.features
    weight = result.features["bpm_histogram_first_peak_weight"]
    assert isinstance(weight, float)
    assert weight > 0.5


def test_bpm_histogram_too_few_intervals():
    pytest.importorskip("essentia", reason="essentia not installed")
    from app.audio.analyzers.bpm_histogram import BpmHistogramAnalyzer

    analyzer = BpmHistogramAnalyzer()
    ctx = AnalysisContext(_make_signal())
    prior: dict[str, Any] = {"beats_intervals": [0.5, 0.5], "beat_times": [0, 0.5, 1.0]}
    result = analyzer.run(ctx, prior)

    assert result.success
    assert result.features.get("bpm_histogram_first_peak_weight") is None


def test_bpm_histogram_graceful_skip_no_essentia():
    from unittest.mock import patch

    with patch.dict("sys.modules", {"essentia": None, "essentia.standard": None}):
        from app.audio.analyzers.bpm_histogram import BpmHistogramAnalyzer

        analyzer = BpmHistogramAnalyzer()
        assert not analyzer.is_available()
