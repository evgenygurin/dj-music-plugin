"""TransitionSelector — orchestrates FX selection and recipe building.

Wraps ``recipe_decision.decide_crossfader_fx_and_bars`` (decides which of the
7 Neural Mix FX to use) and ``recipe_steps.build_steps_for_fx`` (generates
the bar-by-bar stem/EQ playbook for that FX).

This replaces ``style.py:recommend_recipe``, ``recipe_engine.py``, and the
dead pathway through ``TransitionRecipeEngine``.
"""

from __future__ import annotations

from app.core.constants import NeuralMixCrossfaderFX, TechnoSubgenre
from app.entities.audio.features import TrackFeatures
from app.transition.recipe import TransitionRecipe
from app.transition.recipe_decision import (
    clamp_pair_bars,
    decide_crossfader_fx_and_bars,
    rescue_hint,
    resolve_pair_type,
    snap_bars_to_phrase,
)
from app.transition.recipe_steps import build_steps_for_fx
from app.transition.score import TransitionScore
from app.transition.section_context import SectionContext
from app.transition.types import SubgenrePairType, TransitionIntent


class TransitionSelector:
    """Select the best Neural Mix Crossfader FX and build a full recipe.

    Usage::

        selector = TransitionSelector()
        recipe = selector.build_recipe(score, features_a, features_b)

    ``select()`` returns the ``NeuralMixCrossfaderFX`` value only.
    ``build_recipe()`` returns a full ``TransitionRecipe`` with steps.
    """

    def select(
        self,
        score: TransitionScore,
        features_a: TrackFeatures,
        features_b: TrackFeatures,
        *,
        section_context: SectionContext | None = None,
        mood_a: TechnoSubgenre | None = None,
        mood_b: TechnoSubgenre | None = None,
        intent: TransitionIntent | None = None,
    ) -> NeuralMixCrossfaderFX:
        """Return the most appropriate Neural Mix FX for this transition."""
        pair_type = resolve_pair_type(features_a, features_b, mood_a, mood_b)
        fx, _bars, _conf, _warnings = decide_crossfader_fx_and_bars(
            score,
            features_a,
            features_b,
            section_context=section_context,
            pair_type=pair_type,
            intent=intent,
        )
        return fx

    def build_recipe(
        self,
        score: TransitionScore,
        features_a: TrackFeatures,
        features_b: TrackFeatures,
        *,
        section_context: SectionContext | None = None,
        mood_a: TechnoSubgenre | None = None,
        mood_b: TechnoSubgenre | None = None,
        intent: TransitionIntent | None = None,
    ) -> TransitionRecipe:
        """Return a full recipe: FX, bar count, step sequence, and metadata."""
        pair_type = resolve_pair_type(features_a, features_b, mood_a, mood_b)

        fx, raw_bars, confidence, extra_warnings = decide_crossfader_fx_and_bars(
            score,
            features_a,
            features_b,
            section_context=section_context,
            pair_type=pair_type,
            intent=intent,
        )

        bars = snap_bars_to_phrase(clamp_pair_bars(raw_bars, pair_type))
        steps, eq_plan = build_steps_for_fx(fx, bars)

        warnings: list[str] = list(extra_warnings)
        bpm_a = features_a.bpm or 0.0
        bpm_b = features_b.bpm or 0.0
        bpm_delta = abs(bpm_a - bpm_b)
        if bpm_delta > 4.0:
            warnings.append(f"BPM delta {bpm_delta:.1f} — use sync_lock")
        elif bpm_delta > 1.0:
            warnings.append(f"BPM delta {bpm_delta:.1f} — gradual nudge")

        mix_out: str | None = None
        mix_in: str | None = None
        if section_context:
            if section_context.from_section is not None:
                mix_out = section_context.from_section.name.lower()
            if section_context.to_section is not None:
                mix_in = section_context.to_section.name.lower()

        return TransitionRecipe(
            fx_type=fx,
            bars=bars,
            steps=steps,
            eq_plan=eq_plan,
            djay_tempo_adjust=(
                "sync_lock" if bpm_delta >= 4.0 else ("gradual" if bpm_delta >= 1.0 else "none")
            ),
            mix_in_section=mix_in,
            mix_out_section=mix_out,
            phrase_align=bars > 0,
            warnings=tuple(warnings),
            confidence=confidence,
            subgenre_modifier=pair_type.value
            if pair_type != SubgenrePairType.MIXED_PAIR
            else None,
            rescue_move=rescue_hint(fx),
        )
