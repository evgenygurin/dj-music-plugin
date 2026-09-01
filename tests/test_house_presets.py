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


def test_all_presets_within_global_constraints():
    from app.domain.performance.subgenre_presets import PRESET_MAP

    for name, preset in PRESET_MAP.items():
        assert 8 <= preset.transition_bars <= 64, f"{name} transition {preset.transition_bars}"
        assert 8 <= preset.body_bars <= 64, f"{name} body {preset.body_bars}"
        assert 0.75 <= preset.limiter_ceiling <= 0.88, f"{name} limiter {preset.limiter_ceiling}"
        assert 200 <= preset.xsplit_low_hz <= 5500, f"{name} xsplit_low"
        assert 200 <= preset.xsplit_high_hz <= 5500, f"{name} xsplit_high"
        assert preset.xsplit_low_hz < preset.xsplit_high_hz, f"{name} xsplit order"
        assert preset.transition_bars in range(8, 65)
        assert preset.body_bars in range(8, 65)


def test_bar_planner_house_env_override():
    from types import SimpleNamespace

    from app.config.render import RenderSettings
    from app.domain.render.bar_plan import BarPlanner
    from app.domain.render.models import BeatgridEntry

    # direct _config_bar_override fallback for house (TechnoSubgenre miss)
    settings = RenderSettings(transition_bars_deep_house=33, body_bars_deep_house=49)
    planner = BarPlanner(settings)
    assert planner._config_bar_override("deep_house", "transition_bars") == 33
    assert planner._config_bar_override("deep_house", "body_bars") == 49
    # case/space normalization
    assert planner._config_bar_override("Deep House", "transition_bars") == 33
    assert planner._config_bar_override("DEEP_HOUSE", "body_bars") == 49
    # techno still via enum
    settings2 = RenderSettings(transition_bars_hypnotic=99)
    planner2 = BarPlanner(settings2)
    assert planner2._config_bar_override("hypnotic", "transition_bars") == 99
    # compute integration: 2 deep_house tracks with env override
    def _inputs(moods):
        return [
            SimpleNamespace(track_id=i, mood=m, bpm=130.0, duration_ms=300000)
            for i, m in enumerate(moods)
        ]

    def _grid(n):
        return {
            i: BeatgridEntry(
                track_id=i, trim_start_s=0.5, refined_trim_s=0.5, gain_db=0.0, phase_ms=0.0
            )
            for i in range(n)
        }

    plan = BarPlanner(settings).compute(_inputs(["deep_house", "deep_house"]), _grid(2))
    assert plan.transition_bars == (33,)
    assert plan.body_bars == [49, 49]
    # tech_house variant
    s_tech = RenderSettings(transition_bars_tech_house=17)
    p_tech = BarPlanner(s_tech)
    assert p_tech._config_bar_override("tech_house", "transition_bars") == 17
    assert p_tech._config_bar_override("Tech House", "transition_bars") == 17
