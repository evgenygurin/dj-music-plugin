"""Tests for VoicingAnalyzer and picker integration."""

from __future__ import annotations

import numpy as np


class TestVoicingAnalyzer:
    def test_registered(self):
        from app.audio.analyzers.base import AnalyzerRegistry

        registry = AnalyzerRegistry()
        registry.discover()
        assert "voicing" in registry.list_all()

    def test_returns_voicing_ratio(self):
        from app.audio.analyzers.voicing import VoicingAnalyzer
        from app.audio.core.context import AnalysisContext
        from app.audio.core.types import AudioSignal

        sr = 22050
        duration = 2.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        samples = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

        signal = AudioSignal(samples=samples, sample_rate=sr, duration_seconds=duration)
        ctx = AnalysisContext(signal=signal)
        analyzer = VoicingAnalyzer()
        result = analyzer._extract(ctx)

        assert "voicing_ratio" in result
        assert 0.0 <= result["voicing_ratio"] <= 1.0

    def test_noise_has_low_voicing(self):
        from app.audio.analyzers.voicing import VoicingAnalyzer
        from app.audio.core.context import AnalysisContext
        from app.audio.core.types import AudioSignal

        sr = 22050
        duration = 2.0
        samples = np.random.randn(int(sr * duration)).astype(np.float32) * 0.01

        signal = AudioSignal(samples=samples, sample_rate=sr, duration_seconds=duration)
        ctx = AnalysisContext(signal=signal)
        analyzer = VoicingAnalyzer()
        result = analyzer._extract(ctx)

        assert result["voicing_ratio"] < 0.2


class TestPickerWithVoicing:
    def test_voicing_ratio_overrides_spectral_proxy(self):
        from app.domain.transition.picker import _vocal_active
        from app.shared.features import TrackFeatures

        t = TrackFeatures(
            pitch_salience_mean=0.85,
            spectral_centroid_hz=3200.0,
            voicing_ratio=0.1,
        )
        assert _vocal_active(t) is False

    def test_falls_back_to_spectral_when_voicing_missing(self):
        from app.domain.transition.picker import _vocal_active
        from app.shared.features import TrackFeatures

        t = TrackFeatures(
            pitch_salience_mean=0.65,
            spectral_centroid_hz=2800.0,
            voicing_ratio=None,
            energy_bands=[0.05, 0.10, 0.25, 0.25, 0.20, 0.15],
        )
        assert _vocal_active(t) is True
