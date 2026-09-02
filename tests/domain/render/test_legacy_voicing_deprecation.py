"""Tests for legacy stem_voicing module deprecation shim.

This module is kept for one release to allow old imports to keep working.
After Phase 4 cleanup, this file should be removed along with stem_voicing.py.
"""

import importlib
import warnings

import pytest

from app.domain.render.stem_voicing import stem_voicing


def _load_legacy_attr(name: str):
    """Access a legacy attr via __getattr__ to trigger the deprecation warning."""
    mod = importlib.import_module("app.domain.render.stem_voicing")
    return getattr(mod, name)


def test_legacy_stem_voicing_emits_deprecation():
    """Accessing STEM_VOICING via the shim raises DeprecationWarning."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _ = _load_legacy_attr("STEM_VOICING")
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)


def test_legacy_stem_voicing_alias_points_to_stem_timbre():
    """STEM_VOICING shim returns the same dict as STEM_TIMBRE."""
    from app.domain.render.stem_timbre import STEM_TIMBRE

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        legacy = _load_legacy_attr("STEM_VOICING")
    assert legacy is STEM_TIMBRE
    from app.domain.render.models import STEM_ORDER

    assert set(legacy) == set(STEM_ORDER)


def test_legacy_stem_voicing_class_is_stem_timbre():
    """StemVoicing shim returns the new StemTimbre class."""
    from app.domain.render.stem_timbre import StemTimbre

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        klass = _load_legacy_attr("StemVoicing")
    assert klass is StemTimbre


def test_legacy_stem_voicing_function_calls_stem_timbre():
    """stem_voicing() shim delegates to stem_timbre()."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = _load_legacy_attr("stem_voicing")("drums")
    assert result.hpf_hz is None
    assert result.gain_db == 0.0


def test_legacy_voicing_raises_for_legacy_stems():
    """The shim now raises ValueError for removed legacy stems (instrumental, acappella)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        for legacy_stem in ("instrumental", "acappella", "other"):
            with pytest.raises(ValueError):
                stem_voicing(legacy_stem)
