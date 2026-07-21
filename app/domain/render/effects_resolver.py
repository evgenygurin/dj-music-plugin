"""Resolve render-plan effect preset names into value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.audio.effects.echo_delay import ECHO_PRESETS, EchoPlan
from app.audio.effects.filter_sweep import FILTER_PRESETS, TransitionFilterPreset


@dataclass(frozen=True, slots=True)
class ResolvedEffects:
    echo: EchoPlan | None = None
    sweep: TransitionFilterPreset | None = None


class EffectPresetResolver:
    def resolve(self, plan: Any) -> ResolvedEffects:
        return ResolvedEffects(
            echo=self._resolve_echo(plan.echo_preset),
            sweep=self._resolve_sweep(plan.filter_sweep_preset),
        )

    @staticmethod
    def _resolve_echo(name: str | None) -> EchoPlan | None:
        if name is None:
            return None
        return ECHO_PRESETS.get(name)

    @staticmethod
    def _resolve_sweep(name: str | None) -> TransitionFilterPreset | None:
        if name is None:
            return None
        return FILTER_PRESETS.get(name)
