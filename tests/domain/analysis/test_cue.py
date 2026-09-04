import pytest

from app.domain.analysis.cue import CuePoint


def test_cue_point_has_type_and_bar_position() -> None:
    cue = CuePoint(time_s=64.5, kind="mix_in", bar=17, confidence=0.75)
    assert cue.kind == "mix_in"
    assert cue.bar == 17


def test_cue_point_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="time_s"):
        CuePoint(time_s=-1, kind="mix_out")
    with pytest.raises(ValueError, match="kind"):
        CuePoint(time_s=1, kind="bad")
