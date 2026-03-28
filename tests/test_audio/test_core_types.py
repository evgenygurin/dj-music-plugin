"""Tests for core audio types."""

from __future__ import annotations

import numpy as np
import pytest

from app.audio.core.types import AnalyzerResult, AudioSignal, FrameParams


class TestFrameParams:
    def test_defaults(self) -> None:
        fp = FrameParams()
        assert fp.frame_length == 2048
        assert fp.hop_length == 512

    def test_custom_values(self) -> None:
        fp = FrameParams(frame_length=4096, hop_length=1024)
        assert fp.frame_length == 4096
        assert fp.hop_length == 1024

    def test_frozen(self) -> None:
        fp = FrameParams()
        with pytest.raises(AttributeError):
            fp.frame_length = 1024  # type: ignore[misc]


class TestAudioSignal:
    def test_creation(self) -> None:
        samples = np.zeros(1000, dtype=np.float32)
        sig = AudioSignal(samples=samples, sample_rate=22050, duration_seconds=1.0)
        assert sig.sample_rate == 22050
        assert sig.file_path == ""

    def test_file_path_optional(self) -> None:
        sig = AudioSignal(
            samples=np.zeros(100, dtype=np.float32),
            sample_rate=22050,
            duration_seconds=0.1,
            file_path="/tmp/test.wav",
        )
        assert sig.file_path == "/tmp/test.wav"


class TestAnalyzerResult:
    def test_success_defaults(self) -> None:
        r = AnalyzerResult(analyzer_name="test")
        assert r.success is True
        assert r.error is None
        assert r.features == {}

    def test_failure(self) -> None:
        r = AnalyzerResult(analyzer_name="test", success=False, error="boom")
        assert r.success is False
        assert r.error == "boom"

    def test_features_dict(self) -> None:
        r = AnalyzerResult(analyzer_name="test", features={"bpm": 128.0})
        assert r.features["bpm"] == 128.0
