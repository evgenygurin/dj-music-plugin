"""TransitionRecipeEngine — rule-based decision tree for DJ transition recipes.

Selects one of 12 transition types based on scores, audio features, subgenre
pairing, section context, and intent.  Generates step-by-step stem/EQ/effect
instructions consumable by djay Pro AI or a human DJ.

Pure domain logic — no DB, no HTTP, no framework imports.
"""

from __future__ import annotations

from app.core.constants import TechnoSubgenre
from app.entities.audio.features import TrackFeatures
from app.transition.intent import TransitionIntent
from app.transition.recipe import (
    DjayTransition,
    EQPlan,
    RecipeStep,
    StemAction,
    TransitionRecipe,
    TransitionType,
)
from app.transition.score import TransitionScore
from app.transition.section_context import SectionContext
from app.transition.subgenre_rules import SubgenrePairType, clamp_bars, classify_pair

# ── Rescue moves per transition type ──

_RESCUE_MOVES: dict[TransitionType, str] = {
    TransitionType.CUT: "echo out if timing is off",
    TransitionType.BASS_SWAP_SHORT: "filter sweep + hard cut",
    TransitionType.BASS_SWAP_LONG: "filter sweep + hard cut",
    TransitionType.EQ_BLEND: "filter sweep if clash detected",
    TransitionType.FILTER_SWEEP: "hard cut if filter doesn't mask",
    TransitionType.ECHO_OUT: "hard cut",
    TransitionType.LONG_BLEND: "filter sweep + gradual fade",
    TransitionType.RISER: "hard cut on the drop",
    TransitionType.DROP_SWAP: "loop outgoing if mistimed",
    TransitionType.NEURAL_MIX_BLEND: "mute all stems A + hard cut",
    TransitionType.DRUM_SWAP: "hard cut if stems clash",
    TransitionType.DRUM_CUT: "echo out if B drums aren't ready",
    TransitionType.DISSOLVE: "filter sweep",
    TransitionType.STEMS_CREATIVE: "hard cut + echo tail",
}


# ── Phrase snapping ──


def _snap_to_phrase(bars: int) -> int:
    if bars == 0:
        return 0
    if bars <= 4:
        return 4
    return max(8, round(bars / 8) * 8)


# ── Step template builders ──


def _steps_cut(_bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    steps = (RecipeStep(bar=0, deck="both", action="Hard crossfader cut on the one"),)
    return steps, EQPlan(low="keep", mid="keep", high="keep")


def _steps_bass_swap_short(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    h = max(bars // 2, 1)
    q3 = max(bars * 3 // 4, h + 1)
    steps = (
        RecipeStep(
            bar=0,
            deck="B",
            action="Start on phrase boundary, bass EQ killed",
            eq_band="low",
            eq_value=0.0,
        ),
        RecipeStep(
            bar=0,
            deck="B",
            action="Bring in hi-hats and percussion at -6dB",
            eq_band="high",
            eq_value=0.5,
        ),
        RecipeStep(bar=h, deck="B", action="Raise mids gradually", eq_band="mid", eq_value=0.8),
        RecipeStep(
            bar=h,
            deck="both",
            action="BASS SWAP on the one",
            stem="bass",
            stem_action=StemAction.SWAP,
        ),
        RecipeStep(bar=h, deck="A", action="Begin HPF sweep", effect="hpf", effect_param=0.3),
        RecipeStep(
            bar=q3, deck="A", action="HPF 70%, fade volume", effect="hpf", effect_param=0.7
        ),
        RecipeStep(bar=bars, deck="B", action="Full. Release filters. Kill A."),
    )
    return steps, EQPlan(low=f"swap@bar{h}", mid="gradual", high="keep")


def _steps_bass_swap_long(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    q1 = max(bars // 4, 1)
    h = max(bars // 2, 2)
    q3 = max(bars * 3 // 4, h + 1)
    steps = (
        RecipeStep(
            bar=0, deck="B", action="Introduce B with EQ bass killed", eq_band="low", eq_value=0.0
        ),
        RecipeStep(bar=q1, deck="B", action="Gradually bring mids", eq_band="mid", eq_value=0.5),
        RecipeStep(
            bar=h,
            deck="both",
            action="Bass swap on phrase boundary",
            stem="bass",
            stem_action=StemAction.SWAP,
        ),
        RecipeStep(bar=h, deck="A", action="Start cutting A lows", eq_band="low", eq_value=0.3),
        RecipeStep(bar=q3, deck="A", action="HPF sweep on A", effect="hpf", effect_param=0.5),
        RecipeStep(bar=bars, deck="B", action="Full. Kill A."),
    )
    return steps, EQPlan(low=f"swap@bar{h}", mid="gradual", high="gradual")


def _steps_eq_blend(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    q1 = max(bars // 4, 1)
    h = max(bars // 2, 2)
    q3 = max(bars * 3 // 4, h + 1)
    steps = (
        RecipeStep(
            bar=0,
            deck="B",
            action="Bring in B with lows and mids cut",
            eq_band="low",
            eq_value=0.0,
        ),
        RecipeStep(
            bar=q1, deck="B", action="Raise B highs to blend", eq_band="high", eq_value=0.8
        ),
        RecipeStep(
            bar=h,
            deck="both",
            action="Swap bass, cross mids",
            stem="bass",
            stem_action=StemAction.SWAP,
        ),
        RecipeStep(bar=q3, deck="A", action="Cut A mids and highs", eq_band="mid", eq_value=0.2),
        RecipeStep(bar=bars, deck="B", action="Full. Kill A."),
    )
    return steps, EQPlan(low=f"swap@bar{h}", mid="crossfade", high="crossfade")


def _steps_filter_sweep(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    q1 = max(bars // 4, 1)
    h = max(bars // 2, 2)
    q3 = max(bars * 3 // 4, h + 1)
    steps = (
        RecipeStep(
            bar=0, deck="B", action="Start with LPF fully closed", effect="lpf", effect_param=1.0
        ),
        RecipeStep(bar=q1, deck="B", action="Open LPF gradually", effect="lpf", effect_param=0.5),
        RecipeStep(bar=h, deck="A", action="HPF sweep begins", effect="hpf", effect_param=0.3),
        RecipeStep(
            bar=q3, deck="B", action="LPF fully open. A: HPF 80%", effect="lpf", effect_param=0.0
        ),
        RecipeStep(bar=bars, deck="both", action="Crossfader to B. A killed."),
    )
    return steps, EQPlan(low="keep", mid="filter", high="filter")


def _steps_echo_out(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    h = max(bars // 2, 1)
    steps = (
        RecipeStep(bar=0, deck="B", action="Cue B on phrase boundary"),
        RecipeStep(
            bar=0, deck="A", action="Engage echo effect on A", effect="echo", effect_param=0.5
        ),
        RecipeStep(
            bar=h,
            deck="A",
            action="Increase echo wet, fade volume",
            effect="echo",
            effect_param=0.8,
        ),
        RecipeStep(bar=bars, deck="B", action="Full. Kill A echo tail."),
    )
    return steps, EQPlan(low="keep", mid="keep", high="echo_tail")


def _steps_long_blend(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    q1 = max(bars // 4, 1)
    h = max(bars // 2, 2)
    q3 = max(bars * 3 // 4, h + 1)
    steps = (
        RecipeStep(
            bar=0,
            deck="B",
            action="Start B very quietly, highs only",
            eq_band="high",
            eq_value=0.3,
        ),
        RecipeStep(
            bar=q1, deck="B", action="Gradually introduce mids", eq_band="mid", eq_value=0.4
        ),
        RecipeStep(
            bar=h,
            deck="both",
            action="Slow bass crossfade begins",
            stem="bass",
            stem_action=StemAction.SWAP,
        ),
        RecipeStep(bar=q3, deck="A", action="Fade A out gradually"),
        RecipeStep(bar=bars, deck="B", action="Full. A silent."),
    )
    return steps, EQPlan(low=f"swap@bar{h}", mid="gradual", high="gradual")


def _steps_riser(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    h = max(bars // 2, 1)
    steps = (
        RecipeStep(
            bar=0, deck="A", action="Engage riser FX on A", effect="riser", effect_param=0.5
        ),
        RecipeStep(
            bar=h, deck="A", action="Riser intensity builds", effect="riser", effect_param=0.9
        ),
        RecipeStep(bar=bars, deck="both", action="Hard cut to B on the drop"),
    )
    return steps, EQPlan(low="keep", mid="keep", high="riser")


def _steps_drop_swap(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    h = max(bars // 2, 1) if bars > 0 else 0
    steps = (
        RecipeStep(bar=0, deck="A", action="Loop last 4 beats of A"),
        RecipeStep(
            bar=h,
            deck="both",
            action="Drop swap — cut A, slam B on the one",
            stem="bass",
            stem_action=StemAction.CUT,
        ),
        RecipeStep(bar=bars, deck="B", action="B full, release loop"),
    )
    return steps, EQPlan(low="cut", mid="cut", high="cut")


def _steps_neural_mix_blend(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    q1 = max(bars // 4, 1)
    h = max(bars // 2, 2)
    q3 = max(bars * 3 // 4, h + 1)
    steps = (
        RecipeStep(
            bar=0,
            deck="B",
            action="Introduce drums via Neural Mix",
            stem="drums",
            stem_action=StemAction.FADE_IN,
        ),
        RecipeStep(
            bar=q1,
            deck="A",
            action="Fade out harmonics",
            stem="harmonics",
            stem_action=StemAction.FADE_OUT,
        ),
        RecipeStep(
            bar=h,
            deck="both",
            action="Bass swap on phrase",
            stem="bass",
            stem_action=StemAction.SWAP,
        ),
        RecipeStep(
            bar=q3,
            deck="B",
            action="Bring in harmonics",
            stem="harmonics",
            stem_action=StemAction.FADE_IN,
        ),
        RecipeStep(bar=bars, deck="B", action="Full. Kill A."),
    )
    return steps, EQPlan(low=f"swap@bar{h}", mid="gradual", high="gradual")


def _steps_drum_swap(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    """Neural Mix drum swap — swap drum stems on phrase boundary.

    The workhorse techno transition: keep A's melody/bass while fading in B's
    drums, then swap at mid-point. Works even when keys clash — drums are
    non-harmonic. djay Pro: use Neural Mix (Drum Swap) crossfader FX.
    """
    q1 = max(bars // 4, 1)
    h = max(bars // 2, 2)
    q3 = max(bars * 3 // 4, h + 1)
    steps = (
        RecipeStep(
            bar=0,
            deck="B",
            action="Cue B on phrase boundary, drums muted",
            stem="drums",
            stem_action=StemAction.MUTE,
        ),
        RecipeStep(
            bar=q1,
            deck="B",
            action="Fade in B drums via Neural Mix",
            stem="drums",
            stem_action=StemAction.FADE_IN,
        ),
        RecipeStep(
            bar=h,
            deck="A",
            action="Fade out A drums — B drums carry",
            stem="drums",
            stem_action=StemAction.FADE_OUT,
        ),
        RecipeStep(
            bar=q3,
            deck="A",
            action="Fade out A bass + harmonics",
            stem="bass",
            stem_action=StemAction.FADE_OUT,
        ),
        RecipeStep(bar=bars, deck="B", action="B full, A silent"),
    )
    return steps, EQPlan(low="stem", mid="stem", high="stem")


def _steps_drum_cut(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    """Neural Mix drum cut — hard cut A drums at phrase end, B carries.

    Clean, punchy techno move: at phrase boundary, kill A drums entirely
    and let B drums take over. Works best when B already playing underneath.
    djay Pro: use Neural Mix (Drum Cut) crossfader FX.
    """
    q1 = max(bars // 4, 1)
    h = max(bars // 2, 2)
    steps = (
        RecipeStep(
            bar=0,
            deck="B",
            action="Cue B, drums active, low volume",
            stem="drums",
            stem_action=StemAction.SOLO,
        ),
        RecipeStep(
            bar=q1,
            deck="B",
            action="Raise B to full volume",
        ),
        RecipeStep(
            bar=h,
            deck="A",
            action="CUT A drums on the one — B carries",
            stem="drums",
            stem_action=StemAction.CUT,
        ),
        RecipeStep(bar=bars, deck="B", action="B full, A silent"),
    )
    return steps, EQPlan(low="cut", mid="cut", high="cut")


def _steps_dissolve(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    q1 = max(bars // 4, 1)
    h = max(bars // 2, 2)
    q3 = max(bars * 3 // 4, h + 1)
    steps = (
        RecipeStep(bar=0, deck="B", action="Begin B at very low volume"),
        RecipeStep(bar=q1, deck="both", action="Slowly crossfade volume"),
        RecipeStep(bar=h, deck="both", action="Equal volume — textures blend"),
        RecipeStep(bar=q3, deck="A", action="A fades to ambient tail"),
        RecipeStep(bar=bars, deck="B", action="Full. A silent."),
    )
    return steps, EQPlan(low="crossfade", mid="crossfade", high="crossfade")


def _steps_stems_creative(bars: int) -> tuple[tuple[RecipeStep, ...], EQPlan]:
    q1 = max(bars // 4, 1)
    h = max(bars // 2, 2)
    q3 = max(bars * 3 // 4, h + 1)
    steps = (
        RecipeStep(
            bar=0, deck="A", action="Solo A drums", stem="drums", stem_action=StemAction.SOLO
        ),
        RecipeStep(
            bar=q1, deck="B", action="Fade in B bass", stem="bass", stem_action=StemAction.FADE_IN
        ),
        RecipeStep(
            bar=h,
            deck="B",
            action="Fade in B harmonics",
            stem="harmonics",
            stem_action=StemAction.FADE_IN,
        ),
        RecipeStep(
            bar=q3, deck="A", action="Mute A drums", stem="drums", stem_action=StemAction.MUTE
        ),
        RecipeStep(bar=bars, deck="B", action="Full. Kill A."),
    )
    return steps, EQPlan(low="stem", mid="stem", high="stem")


_STEP_BUILDERS: dict[
    TransitionType,
    type[None] | object,  # callable(bars) -> tuple[steps, eq_plan]
] = {
    TransitionType.CUT: _steps_cut,
    TransitionType.BASS_SWAP_SHORT: _steps_bass_swap_short,
    TransitionType.BASS_SWAP_LONG: _steps_bass_swap_long,
    TransitionType.EQ_BLEND: _steps_eq_blend,
    TransitionType.FILTER_SWEEP: _steps_filter_sweep,
    TransitionType.ECHO_OUT: _steps_echo_out,
    TransitionType.LONG_BLEND: _steps_long_blend,
    TransitionType.RISER: _steps_riser,
    TransitionType.DROP_SWAP: _steps_drop_swap,
    TransitionType.NEURAL_MIX_BLEND: _steps_neural_mix_blend,
    TransitionType.DRUM_SWAP: _steps_drum_swap,
    TransitionType.DRUM_CUT: _steps_drum_cut,
    TransitionType.DISSOLVE: _steps_dissolve,
    TransitionType.STEMS_CREATIVE: _steps_stems_creative,
}


# ── Engine ──


class TransitionRecipeEngine:
    """Rule-based decision tree selecting transition type and generating recipes."""

    def generate(
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
        pair_type = classify_pair(
            mood_a or (features_a.mood if features_a.mood else None),
            mood_b or (features_b.mood if features_b.mood else None),
        )

        # Decision tree — first match wins.
        tt, bars, djay, conf, extra_warnings = self._decide(
            score,
            features_a,
            features_b,
            section_context=section_context,
            pair_type=pair_type,
            intent=intent,
        )

        # Post-processing.
        bars = clamp_bars(bars, pair_type)
        bars = _snap_to_phrase(bars)

        # Build steps.
        builder = _STEP_BUILDERS.get(tt, _steps_filter_sweep)
        steps, eq_plan = builder(bars)  # type: ignore[operator]

        # Warnings.
        warnings: list[str] = list(extra_warnings)
        bpm_a = features_a.bpm or 0.0
        bpm_b = features_b.bpm or 0.0
        bpm_delta = abs(bpm_a - bpm_b)
        if bpm_delta > 4.0:
            warnings.append(f"BPM delta {bpm_delta:.1f}")

        # Sections.
        mix_out = None
        mix_in = None
        if section_context:
            if section_context.from_section is not None:
                mix_out = section_context.from_section.name.lower()
            if section_context.to_section is not None:
                mix_in = section_context.to_section.name.lower()

        # Tempo adjust.
        if bpm_delta < 1.0:
            tempo_adj = "none"
        elif bpm_delta < 4.0:
            tempo_adj = "gradual"
        else:
            tempo_adj = "sync_lock"

        return TransitionRecipe(
            transition_type=tt,
            bars=bars,
            djay_transition=djay,
            djay_tempo_adjust=tempo_adj,
            steps=steps,
            eq_plan=eq_plan,
            mix_in_section=mix_in,
            mix_out_section=mix_out,
            phrase_align=bars > 0,
            warnings=tuple(warnings),
            confidence=conf,
            subgenre_modifier=pair_type.value
            if pair_type != SubgenrePairType.MIXED_PAIR
            else None,
            rescue_move=_RESCUE_MOVES.get(tt, "hard cut"),
        )

    # ── Decision tree ──

    def _decide(
        self,
        score: TransitionScore,
        fa: TrackFeatures,
        fb: TrackFeatures,
        *,
        section_context: SectionContext | None,
        pair_type: SubgenrePairType,
        intent: TransitionIntent | None,
    ) -> tuple[TransitionType, int, DjayTransition, float, list[str]]:
        """Return (type, bars, djay_transition, confidence, extra_warnings)."""

        # Step 1: Hard reject.
        if score.hard_reject:
            return TransitionType.FILTER_SWEEP, 16, DjayTransition.FILTER, 0.60, []

        # Step 2: Drum-only pair.
        if section_context and section_context.is_drum_only_pair:
            if score.groove > 0.80:
                return TransitionType.CUT, 0, DjayTransition.NONE, 0.95, []
            if score.groove > 0.60:
                return TransitionType.BASS_SWAP_SHORT, 8, DjayTransition.NONE, 0.88, []
            return TransitionType.FILTER_SWEEP, 8, DjayTransition.FILTER, 0.75, []

        # Step 3: Spectral collision.
        if score.spectral < 0.45:
            return TransitionType.FILTER_SWEEP, 16, DjayTransition.FILTER, 0.80, []

        # Step 4: Key clash — prefer drum-based transitions for techno.
        # Drums are non-harmonic; swapping drums bypasses key incompatibility.
        if score.harmonic < 0.55:
            # Ambient pair: long blend across pads works better than drum swap
            if pair_type == SubgenrePairType.AMBIENT_PAIR:
                return TransitionType.LONG_BLEND, 64, DjayTransition.NONE, 0.72, []
            # Compatible tempo + decent groove → Drum Swap (workhorse techno move)
            if score.bpm > 0.85 and score.groove > 0.50:
                return (
                    TransitionType.DRUM_SWAP,
                    16,
                    DjayTransition.NEURAL_MIX_DRUM_SWAP,
                    0.82,
                    ["key clash — swapping drums to bypass"],
                )
            # Groove strong but BPM shaky → full neural mix blend
            if score.groove > 0.70:
                return (TransitionType.NEURAL_MIX_BLEND, 24, DjayTransition.NEURAL_MIX, 0.80, [])
            # Fallback: echo out
            return TransitionType.ECHO_OUT, 16, DjayTransition.ECHO, 0.70, []

        # Step 5: Energy gap.
        if score.energy < 0.40:
            lufs_a = fa.integrated_lufs or -10.0
            lufs_b = fb.integrated_lufs or -10.0
            delta = lufs_b - lufs_a  # positive = B louder
            if delta > 0:
                if intent == TransitionIntent.RAMP_UP or pair_type == SubgenrePairType.HARD_PAIR:
                    return TransitionType.RISER, 8, DjayTransition.RISER, 0.82, []
                return TransitionType.FILTER_SWEEP, 16, DjayTransition.FILTER, 0.75, []
            # delta <= 0 (energy drop)
            if pair_type == SubgenrePairType.AMBIENT_PAIR:
                return TransitionType.DISSOLVE, 32, DjayTransition.TREMOLO, 0.78, []
            # Energy drop with good groove → Drum Cut (clean phrase-end punch)
            if score.groove > 0.60 and score.bpm > 0.85:
                return (
                    TransitionType.DRUM_CUT,
                    8,
                    DjayTransition.NEURAL_MIX_DRUM_CUT,
                    0.80,
                    ["energy drop — cutting A drums clean"],
                )
            return TransitionType.ECHO_OUT, 16, DjayTransition.ECHO, 0.80, []

        # Step 6a: Drum Swap first — workhorse techno transition.
        # For any non-ambient techno pair with decent rhythm compatibility,
        # Drum Swap is the genre-standard move. It preserves continuity of A's
        # melody/bass while fading in B's drums via Neural Mix — works even
        # when keys are not perfect and BPM is slightly off.
        if (
            pair_type != SubgenrePairType.AMBIENT_PAIR
            and score.groove > 0.55
            and score.overall > 0.55
        ):
            return (
                TransitionType.DRUM_SWAP,
                16,
                DjayTransition.NEURAL_MIX_DRUM_SWAP,
                0.85,
                [],
            )

        # Step 6b: Subgenre-specific fallbacks (when drum swap doesn't fit).
        if pair_type == SubgenrePairType.AMBIENT_PAIR:
            # Ambient dub/dub techno — use drum swap if groove is strong,
            # dissolve only for truly atmospheric pairs with weak percussion.
            if score.groove > 0.60:
                return (
                    TransitionType.DRUM_SWAP,
                    32,
                    DjayTransition.NEURAL_MIX_DRUM_SWAP,
                    0.82,
                    [],
                )
            return TransitionType.DISSOLVE, 48, DjayTransition.TREMOLO, 0.85, []
        if pair_type == SubgenrePairType.HARD_PAIR and score.overall > 0.70:
            # Hard techno — drum cut is cleaner than drop swap for most pairs
            if score.bpm > 0.85 and score.groove > 0.65:
                return (
                    TransitionType.DRUM_CUT,
                    8,
                    DjayTransition.NEURAL_MIX_DRUM_CUT,
                    0.88,
                    [],
                )
            return TransitionType.DROP_SWAP, 4, DjayTransition.NONE, 0.88, []
        if pair_type == SubgenrePairType.ACID_PAIR and score.spectral > 0.60:
            return TransitionType.FILTER_SWEEP, 16, DjayTransition.FILTER, 0.85, []
        if pair_type == SubgenrePairType.HYPNOTIC_PAIR and score.groove > 0.70:
            return (TransitionType.NEURAL_MIX_BLEND, 32, DjayTransition.NEURAL_MIX, 0.83, [])

        # Step 7: Vocal conflict.
        ps_a = fa.pitch_salience_mean or 0.0
        ps_b = fb.pitch_salience_mean or 0.0
        sc_a = fa.spectral_centroid_hz or 0.0
        sc_b = fb.spectral_centroid_hz or 0.0
        if ps_a > 0.4 and ps_b > 0.4 and sc_a > 2500 and sc_b > 2500:
            if score.overall > 0.75:
                return (
                    TransitionType.DROP_SWAP,
                    4,
                    DjayTransition.NONE,
                    0.80,
                    ["vocal overlap risk"],
                )
            return (
                TransitionType.NEURAL_MIX_BLEND,
                16,
                DjayTransition.NEURAL_MIX,
                0.75,
                ["vocal overlap risk"],
            )

        # Step 8: Perfect match.
        if score.bpm > 0.95 and score.harmonic > 0.85 and score.groove > 0.75:
            if pair_type == SubgenrePairType.HARD_PAIR:
                return TransitionType.CUT, 0, DjayTransition.NONE, 0.95, []
            return TransitionType.BASS_SWAP_SHORT, 8, DjayTransition.NONE, 0.92, []

        # Steps 9-12: Graduated fallback.
        # For techno with compatible rhythm, alternate bass_swap and drum_swap
        # to keep the set varied — 4+ consecutive bass_swaps sound monotonous.
        if score.overall > 0.80:
            # Mix in drum_swap when groove is strong — feels more dynamic
            if score.groove > 0.75 and score.bpm > 0.90:
                return (
                    TransitionType.DRUM_SWAP,
                    16,
                    DjayTransition.NEURAL_MIX_DRUM_SWAP,
                    0.88,
                    [],
                )
            return TransitionType.BASS_SWAP_SHORT, 8, DjayTransition.NONE, 0.88, []
        if score.overall > 0.65:
            # EQ blend is classic; drum_swap is more modern techno feel
            if score.groove > 0.65 and pair_type in (
                SubgenrePairType.HARD_PAIR,
                SubgenrePairType.HYPNOTIC_PAIR,
            ):
                return (
                    TransitionType.DRUM_SWAP,
                    16,
                    DjayTransition.NEURAL_MIX_DRUM_SWAP,
                    0.82,
                    [],
                )
            return TransitionType.EQ_BLEND, 16, DjayTransition.NONE, 0.80, []
        if score.overall > 0.50:
            return TransitionType.BASS_SWAP_LONG, 32, DjayTransition.NONE, 0.72, []
        return TransitionType.FILTER_SWEEP, 16, DjayTransition.FILTER, 0.65, []
