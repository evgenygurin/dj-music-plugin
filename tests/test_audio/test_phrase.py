"""Tests for PhraseAnalyzer."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from dj_music.audio.core.context import AnalysisContext
from dj_music.audio.core.types import AudioSignal

SAMPLE_RATE = 22050


def _make_signal(duration: float = 30.0) -> AudioSignal:
    n = int(SAMPLE_RATE * duration)
    rng = np.random.default_rng(42)
    samples = (0.3 * rng.standard_normal(n)).astype(np.float32)
    return AudioSignal(samples=samples, sample_rate=SAMPLE_RATE, duration_seconds=duration)


def _beat_times_for_bpm(bpm: float, duration: float) -> list[float]:
    interval = 60.0 / bpm
    return [i * interval for i in range(int(duration / interval))]


def test_phrase_happy_path():
    pytest.importorskip("librosa", reason="librosa not installed")
    from dj_music.audio.analyzers.phrase import PhraseAnalyzer

    analyzer = PhraseAnalyzer()
    ctx = AnalysisContext(_make_signal(duration=60.0))
    prior: dict[str, Any] = {"beat_times": _beat_times_for_bpm(130.0, 60.0)}
    result = analyzer.run(ctx, prior)

    assert result.success
    assert "phrase_boundaries_ms" in result.features
    assert "dominant_phrase_bars" in result.features
    boundaries = result.features["phrase_boundaries_ms"]
    assert isinstance(boundaries, list)
    assert all(isinstance(b, int) for b in boundaries)
    dominant = result.features["dominant_phrase_bars"]
    assert dominant in (8, 16, 32)


def test_phrase_too_few_beats():
    pytest.importorskip("librosa", reason="librosa not installed")
    from dj_music.audio.analyzers.phrase import PhraseAnalyzer

    analyzer = PhraseAnalyzer()
    ctx = AnalysisContext(_make_signal(duration=5.0))
    prior: dict[str, Any] = {"beat_times": [0.0, 0.5, 1.0, 1.5]}
    result = analyzer.run(ctx, prior)

    assert result.success
    assert result.features["phrase_boundaries_ms"] == []
    assert result.features["dominant_phrase_bars"] == 16


def test_phrase_graceful_skip_no_librosa():
    from unittest.mock import patch

    with patch.dict("sys.modules", {"librosa": None}):
        from dj_music.audio.analyzers.phrase import PhraseAnalyzer

        analyzer = PhraseAnalyzer()
        assert not analyzer.is_available()
