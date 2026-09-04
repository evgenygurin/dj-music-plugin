from dataclasses import FrozenInstanceError

import pytest

from app.domain.analysis.tempo import TempoHypothesis


def test_tempo_hypothesis_supports_octave_interpretations() -> None:
    hypothesis = TempoHypothesis(bpm=128.0, confidence=0.9, source="beat")
    assert hypothesis.variants() == (64.0, 128.0, 256.0)


def test_tempo_hypothesis_validates_bpm_and_confidence() -> None:
    with pytest.raises(ValueError, match="bpm"):
        TempoHypothesis(bpm=0, confidence=0.5)
    with pytest.raises(ValueError, match="confidence"):
        TempoHypothesis(bpm=128, confidence=1.1)


def test_tempo_hypothesis_is_immutable() -> None:
    hypothesis = TempoHypothesis(bpm=128, confidence=0.9)
    with pytest.raises(FrozenInstanceError):
        hypothesis.bpm = 129  # type: ignore[misc]
