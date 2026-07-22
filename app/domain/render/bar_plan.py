"""Bar-amount planning per track on the render timeline.

``BarPlan.__iter__`` preserves legacy unpacking while callers migrate from a
bare ``tuple[list[int], list[int]]`` return value.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from app.config.render import RenderSettings
from app.domain.render.models import BeatgridEntry
from app.domain.transition.subgenre_rules import (
    body_bars_for_pair,
    classify_pair,
    transition_bars_for_pair,
)
from app.shared.constants import TechnoSubgenre


@dataclass(frozen=True, slots=True)
class BarPlan:
    """Per-track body bars plus per-pair transition bars."""

    transition_bars: tuple[int, ...]
    body_bars: list[int]

    def __len__(self) -> int:
        return len(self.body_bars)

    def transition_for(self, i: int) -> int:
        return self.transition_bars[i]

    def body_for(self, i: int) -> int:
        return self.body_bars[i]

    def __iter__(self) -> Iterator[tuple[int, ...] | list[int]]:
        yield self.transition_bars
        yield self.body_bars


class BarPlanner:
    def __init__(self, settings: RenderSettings) -> None:
        self._settings = settings

    def compute(
        self,
        inputs: list[Any],
        grid: dict[int, BeatgridEntry],
        transition_bars_override: int | None = None,
        body_bars_override: int | None = None,
        *,
        transition_override: int | None = None,
        body_override: int | None = None,
    ) -> BarPlan:
        if transition_override is not None:
            transition_bars_override = transition_override
        if body_override is not None:
            body_bars_override = body_override

        per_transition: list[int] = []
        per_body: list[int] = []
        for i, ti in enumerate(inputs):
            mood = getattr(ti, "mood", None)
            if i < len(inputs) - 1:
                next_mood = getattr(inputs[i + 1], "mood", None)
                if transition_bars_override is not None:
                    per_transition.append(transition_bars_override)
                else:
                    pair = classify_pair(mood, next_mood)
                    per_transition.append(
                        self._config_or_default(
                            mood, "transition_bars", transition_bars_for_pair(pair)
                        )
                    )

            if body_bars_override is not None:
                per_body.append(body_bars_override)
            else:
                body_pair = classify_pair(mood, None)
                per_body.append(
                    self._config_or_default(mood, "body_bars", body_bars_for_pair(body_pair))
                )

        per_body = self._clamp_to_source_duration(inputs, grid, per_transition, per_body)
        return BarPlan(tuple(per_transition), per_body)

    def _config_or_default(self, mood: Any, prefix: str, default: int) -> int:
        override = self._config_bar_override(mood, prefix)
        if override is not None:
            return override
        return default

    def _config_bar_override(
        self,
        subgenre: TechnoSubgenre | str | None,
        prefix: str,
    ) -> int | None:
        if subgenre is None:
            return None
        if isinstance(subgenre, str):
            try:
                subgenre = TechnoSubgenre(subgenre)
            except ValueError:
                return None
        field_name = f"{prefix}_{subgenre.value}"
        return getattr(self._settings, field_name, None)

    def _clamp_to_source_duration(
        self,
        inputs: list[Any],
        grid: dict[int, BeatgridEntry],
        per_transition: list[int],
        per_body: list[int],
    ) -> list[int]:
        target_bpm = self._settings.target_bpm
        bar_s = 4.0 * (60.0 / target_bpm)
        clamped = list(per_body)
        for i, ti in enumerate(inputs):
            duration_ms = getattr(ti, "duration_ms", None)
            if not duration_ms:
                continue
            d_in = per_transition[i - 1] * bar_s if i > 0 else 0.0
            d_out = per_transition[i] * bar_s if i < len(inputs) - 1 else 0.0
            g = grid.get(ti.track_id)
            trim = g.effective_trim if g is not None else 0.0
            available_source_s = max(0.0, duration_ms / 1000.0 - trim - 1.0)
            ratio = ti.tempo_ratio(target_bpm)
            max_output_s = available_source_s / ratio if ratio > 0 else available_source_s
            body_budget_s = max_output_s - d_in - d_out
            if body_budget_s <= 0:
                clamped[i] = 1
                continue
            max_body_bars = max(1, int(body_budget_s // bar_s))
            clamped[i] = min(clamped[i], max_body_bars)
        return clamped
