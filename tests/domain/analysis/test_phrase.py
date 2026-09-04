import pytest

from app.domain.analysis.phrase import Phrase


def test_phrase_uses_bar_and_second_boundaries() -> None:
    phrase = Phrase(start_s=10.0, end_s=25.0, start_bar=9, end_bar=17, confidence=0.8)
    assert phrase.duration_s == pytest.approx(15.0)
    assert phrase.bar_count == 8


def test_phrase_rejects_invalid_interval_or_confidence() -> None:
    with pytest.raises(ValueError, match="end_s"):
        Phrase(start_s=10, end_s=10, start_bar=1, end_bar=2)
    with pytest.raises(ValueError, match="confidence"):
        Phrase(start_s=0, end_s=1, start_bar=1, end_bar=2, confidence=-0.1)
