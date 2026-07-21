from types import SimpleNamespace

from app.domain.render.effects_resolver import EffectPresetResolver, ResolvedEffects
from app.domain.render.models import RenderMode


def _plan(*, echo: str | None = None, sweep: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(echo_preset=echo, filter_sweep_preset=sweep, mode=RenderMode.CLASSIC)


def test_resolver_returns_none_when_no_presets() -> None:
    fx = EffectPresetResolver().resolve(_plan())
    assert isinstance(fx, ResolvedEffects)
    assert fx.echo is None
    assert fx.sweep is None


def test_resolver_returns_known_echo_preset() -> None:
    fx = EffectPresetResolver().resolve(_plan(echo="techno_standard"))
    assert fx.echo is not None
    assert fx.echo.wet_dry_ratio > 0


def test_resolver_returns_none_for_unknown_echo_preset() -> None:
    fx = EffectPresetResolver().resolve(_plan(echo="not_a_preset"))
    assert fx.echo is None


def test_resolver_returns_known_sweep_preset() -> None:
    fx = EffectPresetResolver().resolve(_plan(sweep="classic_lowpass"))
    assert fx.sweep is not None
    assert fx.sweep.outgoing is not None
    assert fx.sweep.outgoing.end_freq_hz == 200


def test_resolver_returns_none_for_unknown_sweep_preset() -> None:
    fx = EffectPresetResolver().resolve(_plan(sweep="not_a_preset"))
    assert fx.sweep is None
