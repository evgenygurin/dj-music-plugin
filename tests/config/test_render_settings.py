from app.config import get_settings, reset_settings_cache
from app.config.render import RenderSettings


def test_render_settings_defaults():
    s = RenderSettings()
    assert s.target_bpm == 130.0
    assert s.transition_bars == 32
    assert s.body_bars == 24
    assert s.xsplit_low_hz == 250
    assert s.xsplit_high_hz == 4000
    assert s.eq_phase_1_ratio == 0.40
    assert s.eq_phase_2_ratio == 0.70
    assert s.low_swap_beats == 1.0
    assert s.outro_fade_bars == 12
    assert s.limiter_ceiling == 0.85
    assert round(s.beat_s, 4) == 0.4615
    assert round(s.bar_s, 4) == 1.8462


def test_render_settings_on_aggregate():
    reset_settings_cache()
    assert get_settings().render.target_bpm == 130.0


def test_render_env_override(monkeypatch):
    monkeypatch.setenv("DJ_RENDER_TARGET_BPM", "128")
    assert RenderSettings().target_bpm == 128.0
