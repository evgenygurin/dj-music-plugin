from app.domain.render.eq import build_master_eq, build_per_track_eq, build_preprocess_filter
from app.shared.features import TrackFeatures


def test_build_master_eq_returns_firequalizer():
    result = build_master_eq()
    assert result.startswith("entry(")
    assert "1.5" in result  # air boost at 11840
    assert "-1.0" in result  # mud cut at 370


def test_build_per_track_eq_dark_track():
    feat = TrackFeatures(spectral_centroid_hz=1500.0)
    result = build_per_track_eq(feat)
    assert any(float(p.split(",")[1].rstrip("):'")) > 0 for p in result.split("entry(") if "11840" in p or "8372" in p)


def test_build_per_track_eq_bright_track():
    feat = TrackFeatures(spectral_centroid_hz=3500.0)
    result = build_per_track_eq(feat)
    assert any(float(p.split(",")[1].rstrip("):'")) < 0 for p in result.split("entry(") if "2960" in p)


def test_build_per_track_eq_neutral_track():
    feat = TrackFeatures(spectral_centroid_hz=2500.0)
    result = build_per_track_eq(feat)
    assert "11840" in result
    assert "370,0.0" in result or "370,-0.5" in result


def test_build_preprocess_filter():
    result = build_preprocess_filter(1.0, -2.5, "firequalizer=gain_entry='entry(100,0)'")
    assert "highpass=f=30:t=4" in result
    assert "volume=-2.50dB" in result
    assert "acompressor=threshold=-18dB" in result
    assert "ratio=3" in result
    assert "attack=10" in result
    assert "release=80" in result
