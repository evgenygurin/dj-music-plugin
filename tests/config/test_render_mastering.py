from app.config.render import RenderSettings


def test_mastering_defaults():
    s = RenderSettings()
    assert s.hpf_cutoff_hz == 30.0
    assert s.pre_comp_threshold_db == -16.0
    assert s.pre_comp_ratio == 2.5
    assert s.glue_comp_ratio == 2.5
    assert s.master_eq_air_boost_db == 1.0
    assert s.limiter_attack_ms == 12.0
    assert s.limiter_release_ms == 40.0
    assert s.dynaudnorm_maxgain == 2.5
