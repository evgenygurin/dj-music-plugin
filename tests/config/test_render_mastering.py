from app.config.render import RenderSettings


def test_mastering_defaults():
    s = RenderSettings()
    assert s.hpf_cutoff_hz == 30.0
    assert s.pre_comp_threshold_db == -18.0
    assert s.pre_comp_ratio == 3.0
    assert s.glue_comp_ratio == 3.0
    assert s.master_eq_air_boost_db == 1.5
    assert s.limiter_attack_ms == 10.0
    assert s.limiter_release_ms == 30.0
    assert s.dynaudnorm_maxgain == 2.0
