from __future__ import annotations

import numpy as np
import pytest

from app.audio.analyzers.audio_qa import AudioQAAnalyzer
from app.audio.analyzers.chords import ChordsAnalyzer
from app.audio.analyzers.hpcp_extended import HpCPExtendedAnalyzer
from app.audio.analyzers.inharmonicity import InharmonicityAnalyzer
from app.audio.analyzers.meter import MeterAnalyzer


@pytest.fixture
def fake_signal() -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.random(44100 * 5).astype(np.float32) * 0.3  # 5 sec


def test_chords_analyzer_returns_expected_keys(fake_signal: np.ndarray) -> None:
    analyzer = ChordsAnalyzer()
    result = analyzer.analyze(fake_signal, sample_rate=44100)
    assert "chords_strength" in result
    assert "chords_changes_rate" in result


def test_hpcp_extended_returns_expected_keys(fake_signal: np.ndarray) -> None:
    analyzer = HpCPExtendedAnalyzer()
    result = analyzer.analyze(fake_signal, sample_rate=44100)
    assert "hpcp_entropy" in result
    assert "hpcp_crest" in result


def test_inharmonicity_returns_expected_keys(fake_signal: np.ndarray) -> None:
    analyzer = InharmonicityAnalyzer()
    result = analyzer.analyze(fake_signal, sample_rate=44100)
    assert "inharmonicity" in result


def test_meter_returns_expected_keys(fake_signal: np.ndarray) -> None:
    analyzer = MeterAnalyzer()
    result = analyzer.analyze(fake_signal, sample_rate=44100)
    assert "meter" in result


def test_audio_qa_returns_expected_keys(fake_signal: np.ndarray) -> None:
    analyzer = AudioQAAnalyzer()
    result = analyzer.analyze(fake_signal, sample_rate=44100)
    assert "click_detected" in result
    assert "saturation_detected" in result
