from app.domain.render.models import STEM_ORDER
from app.domain.render.stem_voicing import STEM_VOICING


def test_voicing_defined_for_every_stem_in_order():
    assert set(STEM_VOICING) == set(STEM_ORDER)


def test_drums_and_bass_have_no_hpf():
    assert STEM_VOICING["drums"].hpf_hz is None
    assert STEM_VOICING["bass"].hpf_hz is None


def test_harmonic_uses_80hz_hpf_at_minus_2db():
    assert STEM_VOICING["harmonic"].hpf_hz == 80
    assert STEM_VOICING["harmonic"].gain_db == -2.0


def test_instrumental_uses_120hz_hpf_at_minus_7db():
    assert STEM_VOICING["instrumental"].hpf_hz == 120
    assert STEM_VOICING["instrumental"].gain_db == -7.0


def test_acappella_uses_120hz_hpf_at_minus_3db():
    assert STEM_VOICING["acappella"].hpf_hz == 120
    assert STEM_VOICING["acappella"].gain_db == -3.0


def test_drums_and_bass_have_zero_gain():
    assert STEM_VOICING["drums"].gain_db == 0.0
    assert STEM_VOICING["bass"].gain_db == 0.0
