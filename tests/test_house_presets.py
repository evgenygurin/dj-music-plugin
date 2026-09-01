"""House preset TDD — Task 1."""

from __future__ import annotations


def test_deep_house_preset_exists():
    from app.domain.performance.subgenre_presets import resolve_preset

    assert resolve_preset("deep_house") is not None
    assert resolve_preset("tech_house").transition_bars == 16


def test_tech_house_preset_values():
    from app.domain.performance.subgenre_presets import TECH_HOUSE, resolve_preset

    preset = resolve_preset("tech_house")
    assert preset is not None
    assert preset is TECH_HOUSE
    assert preset.transition_bars == 16
    assert preset.body_bars == 32
    assert preset.limiter_ceiling == 0.82


def test_progressive_house_preset_values():
    from app.domain.performance.subgenre_presets import PROGRESSIVE_HOUSE, resolve_preset

    preset = resolve_preset("progressive_house")
    assert preset is not None
    assert preset is PROGRESSIVE_HOUSE
    assert preset.transition_bars == 32
    assert preset.body_bars == 56
    assert preset.limiter_ceiling == 0.85


def test_classic_house_preset_values():
    from app.domain.performance.subgenre_presets import CLASSIC_HOUSE, resolve_preset

    preset = resolve_preset("classic_house")
    assert preset is not None
    assert preset is CLASSIC_HOUSE
    assert preset.transition_bars == 16
    assert preset.body_bars == 32
    assert preset.limiter_ceiling == 0.85
