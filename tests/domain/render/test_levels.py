# tests/domain/render/test_levels.py
from app.domain.render.levels import gains_to_median


def test_gain_toward_median():
    lufs = {1: -12.0, 2: -10.0, 3: -14.0}  # median -12
    g = gains_to_median(lufs)
    assert g[1] == 0.0
    assert g[2] == -1.5  # louder track pulled down conservatively
    assert g[3] == 1.5  # quieter track pushed up conservatively


def test_gain_clamped_to_4db():
    lufs = {1: -12.0, 2: -30.0}  # median -21 -> track1 gain -9 clamps to -4
    g = gains_to_median(lufs)
    assert g[1] == -1.5
    assert g[2] == 1.5


def test_missing_lufs_zero_gain():
    g = gains_to_median({1: None, 2: -12.0})
    assert g[1] == 0.0
