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


def test_render_settings_house_fields():
    from app.config.render import RenderSettings

    s = RenderSettings()
    assert hasattr(s, "transition_bars_deep_house")
    assert s.transition_bars_deep_house is None


def test_preset_map_house():
    from app.domain.performance.subgenre_presets import PRESET_MAP

    assert "deep_house" in PRESET_MAP
    assert "tech_house" in PRESET_MAP
    assert "progressive_house" in PRESET_MAP
    assert "classic_house" in PRESET_MAP
    assert PRESET_MAP["deep_house"].transition_bars == 32
    assert PRESET_MAP["tech_house"].transition_bars == 16
    assert PRESET_MAP["progressive_house"].transition_bars == 32
    assert PRESET_MAP["classic_house"].transition_bars == 16
    # idempotency: total 18 entries (14 techno + 4 house)
    assert len(PRESET_MAP) == 18


def test_resolve_preset_house_suffix():
    from app.domain.performance.subgenre_presets import DEEP_HOUSE, TECH_HOUSE, resolve_preset

    # direct lower snake already works
    assert resolve_preset("deep_house") is DEEP_HOUSE
    # short form via _house suffix fallback
    assert resolve_preset("deep") is DEEP_HOUSE
    assert resolve_preset("tech") is TECH_HOUSE
    # case/space normalization + suffix
    assert resolve_preset("Deep") is DEEP_HOUSE
    assert resolve_preset("deep house") is DEEP_HOUSE
    assert resolve_preset("TECH") is TECH_HOUSE
    # techno suffix still works
    from app.domain.performance.subgenre_presets import INDUSTRIAL

    assert resolve_preset("industrial") is INDUSTRIAL
    assert resolve_preset("Industrial Techno") is INDUSTRIAL


def test_resolve_preset_by_subgenre_house_suffix():
    from app.domain.performance.subgenre_presets import DEEP_HOUSE, resolve_preset_by_subgenre

    assert resolve_preset_by_subgenre("deep_house") is DEEP_HOUSE
    assert resolve_preset_by_subgenre("deep") is DEEP_HOUSE
    assert resolve_preset_by_subgenre("Deep House") is DEEP_HOUSE
    # techno fallback still works
    from app.domain.performance.subgenre_presets import INDUSTRIAL

    assert resolve_preset_by_subgenre("industrial") is INDUSTRIAL
