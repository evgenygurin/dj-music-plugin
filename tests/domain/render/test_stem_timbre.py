"""Tests for stem_timbre module (replaces stem_voicing)."""

import pytest

from app.domain.render.models import STEM_ORDER
from app.domain.render.stem_timbre import STEM_TIMBRE, StemTimbre, stem_timbre


def test_stem_timbre_defined_for_every_stem_in_order():
    """STEM_TIMBRE has an entry for every stem in STEM_ORDER."""
    assert set(STEM_TIMBRE) == set(STEM_ORDER)


def test_drums_and_bass_have_no_hpf():
    """Drums and bass: no HPF, preserve sub fundamentals."""
    assert STEM_TIMBRE["drums"].hpf_hz is None
    assert STEM_TIMBRE["bass"].hpf_hz is None


def test_harmonic_uses_80hz_hpf_at_minus_2db():
    """Harmonic: 80 Hz HPF, -2 dB."""
    assert STEM_TIMBRE["harmonic"].hpf_hz == 80
    assert STEM_TIMBRE["harmonic"].gain_db == -2.0


def test_vocals_uses_120hz_hpf():
    """Vocals: 120 Hz HPF to remove sub-bass bleed."""
    assert STEM_TIMBRE["vocals"].hpf_hz == 120
    assert STEM_TIMBRE["vocals"].gain_db == 0.0


def test_percussion_uses_120hz_hpf():
    """Percussion: 120 Hz HPF to remove kick bleed (per design)."""
    assert STEM_TIMBRE["percussion"].hpf_hz == 120
    assert STEM_TIMBRE["percussion"].gain_db == 0.0


def test_stem_timbre_raises_for_unknown_stem():
    """Unknown stems raise ValueError."""
    with pytest.raises(ValueError):
        stem_timbre("instrumental")  # legacy alias, not allowed in new taxonomy


def test_stem_timbre_raises_for_legacy_stems():
    """Legacy stems (instrumental, acappella, other) raise ValueError."""
    for legacy in ("instrumental", "acappella", "other"):
        with pytest.raises(ValueError):
            stem_timbre(legacy)


def test_stem_timbre_dataclass_is_frozen():
    """StemTimbre is frozen and slotted."""
    timbre = StemTimbre(hpf_hz=80, gain_db=-2.0)
    with pytest.raises(Exception):
        timbre.hpf_hz = 100  # type: ignore[misc]
