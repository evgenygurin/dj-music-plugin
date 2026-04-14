"""Decision tree: map scores + features -> Neural Mix Crossfader FX + bars.

Pure domain: no I/O. Extracted from the former monolithic ``recipe_engine`` so
the engine class only orchestrates — **Single Responsibility** / **KISS**.
"""

from __future__ import annotations

from app.config import settings
from app.core.constants import NeuralMixCrossfaderFX, TechnoSubgenre
from app.entities.audio.features import TrackFeatures
from app.transition.intent import TransitionIntent
from app.transition.score import TransitionScore
from app.transition.section_context import SectionContext
from app.transition.subgenre_rules import clamp_bars, classify_pair
from app.transition.types import SubgenrePairType

# Per-FX fallback hints when the DJ must recover manually (shown in ``rescue_move``).
_RESCUE: dict[NeuralMixCrossfaderFX, str] = {
    NeuralMixCrossfaderFX.NEURAL_MIX_FADE: "if clash persists, shorten overlap",
    NeuralMixCrossfaderFX.NEURAL_MIX_ECHO_OUT: "trim echo time if mud builds",
    NeuralMixCrossfaderFX.NEURAL_MIX_VOCAL_SUSTAIN: "watch phrase — release vocal on bar one",
    NeuralMixCrossfaderFX.NEURAL_MIX_HARMONIC_SUSTAIN: "ease harmonic hold if key fights B",
    NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP: "nudge B phase if kick flam",
    NeuralMixCrossfaderFX.NEURAL_MIX_VOCAL_CUT: "if B has vox too, use shorter blend",
    NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_CUT: "echo out if B drums not tight",
}


def decide_crossfader_fx_and_bars(
    score: TransitionScore,
    fa: TrackFeatures,
    fb: TrackFeatures,
    *,
    section_context: SectionContext | None,
    pair_type: SubgenrePairType,
    intent: TransitionIntent | None,
) -> tuple[NeuralMixCrossfaderFX, int, float, list[str]]:
    """Return ``(fx, bars, confidence, extra_warnings)`` before phrase snapping."""
    # 1 Hard reject — safest is full Neural Mix Fade at low confidence
    if score.hard_reject:
        return NeuralMixCrossfaderFX.NEURAL_MIX_FADE, 16, 0.60, []

    # 2 Drum-only regions (intro/outro/sustain/ambient): rhythm-first FX
    if section_context and section_context.is_drum_only_pair:
        if score.groove > settings.recipe_drum_only_groove_cut_threshold:
            return NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_CUT, 0, 0.95, []
        if score.groove > settings.recipe_drum_only_groove_swap_threshold:
            return NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP, 8, 0.88, []
        return NeuralMixCrossfaderFX.NEURAL_MIX_FADE, 8, 0.75, []

    # 3 Spectral collision — stem-balanced fade clears the mask
    if score.spectral < settings.recipe_spectral_collision_threshold:
        return NeuralMixCrossfaderFX.NEURAL_MIX_FADE, 16, 0.80, []

    # 4 Key clash
    if score.harmonic < settings.recipe_harmonic_clash_threshold:
        if pair_type == SubgenrePairType.AMBIENT_PAIR:
            return NeuralMixCrossfaderFX.NEURAL_MIX_HARMONIC_SUSTAIN, 64, 0.72, []
        if (
            score.bpm > settings.recipe_key_clash_bpm_floor
            and score.groove > settings.recipe_key_clash_groove_floor
        ):
            return (
                NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP,
                16,
                0.82,
                ["key clash — drum stem swap"],
            )
        if score.groove > settings.recipe_key_clash_groove_strong:
            return NeuralMixCrossfaderFX.NEURAL_MIX_FADE, 24, 0.80, []
        return NeuralMixCrossfaderFX.NEURAL_MIX_ECHO_OUT, 16, 0.70, []

    # 5 Energy gap
    if score.energy < settings.recipe_energy_gap_score_threshold:
        lufs_a = fa.integrated_lufs or -10.0
        lufs_b = fb.integrated_lufs or -10.0
        delta = lufs_b - lufs_a
        if delta > 0:
            if intent == TransitionIntent.RAMP_UP or pair_type == SubgenrePairType.HARD_PAIR:
                return NeuralMixCrossfaderFX.NEURAL_MIX_ECHO_OUT, 8, 0.82, []
            return NeuralMixCrossfaderFX.NEURAL_MIX_FADE, 16, 0.75, []
        if pair_type == SubgenrePairType.AMBIENT_PAIR:
            return NeuralMixCrossfaderFX.NEURAL_MIX_HARMONIC_SUSTAIN, 32, 0.78, []
        if (
            score.groove > settings.recipe_energy_drop_groove_floor
            and score.bpm > settings.recipe_energy_drop_bpm_floor
        ):
            return (
                NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_CUT,
                8,
                0.80,
                ["energy drop — drum handoff"],
            )
        return NeuralMixCrossfaderFX.NEURAL_MIX_ECHO_OUT, 16, 0.80, []

    # 6a Default techno: drum swap when groove + overall are healthy
    if (
        pair_type != SubgenrePairType.AMBIENT_PAIR
        and score.groove > settings.recipe_drum_swap_groove_floor
        and score.overall > settings.recipe_drum_swap_overall_floor
    ):
        return NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP, 16, 0.85, []

    # 6b Subgenre branches
    if pair_type == SubgenrePairType.AMBIENT_PAIR:
        if score.groove > settings.recipe_ambient_groove_swap_floor:
            return NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP, 32, 0.82, []
        return NeuralMixCrossfaderFX.NEURAL_MIX_HARMONIC_SUSTAIN, 48, 0.85, []
    if (
        pair_type == SubgenrePairType.HARD_PAIR
        and score.overall > settings.recipe_hard_pair_overall_floor
    ):
        if (
            score.bpm > settings.recipe_hard_pair_bpm_floor
            and score.groove > settings.recipe_hard_pair_groove_floor
        ):
            return NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_CUT, 8, 0.88, []
        return NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP, 4, 0.88, []
    if (
        pair_type == SubgenrePairType.ACID_PAIR
        and score.spectral > settings.recipe_acid_spectral_floor
    ):
        return NeuralMixCrossfaderFX.NEURAL_MIX_FADE, 16, 0.85, []
    if (
        pair_type == SubgenrePairType.HYPNOTIC_PAIR
        and score.groove > settings.recipe_hypnotic_groove_floor
    ):
        return NeuralMixCrossfaderFX.NEURAL_MIX_FADE, 32, 0.83, []

    # 7 Vocal overlap risk (pitch-heavy both sides)
    ps_a = fa.pitch_salience_mean or 0.0
    ps_b = fb.pitch_salience_mean or 0.0
    sc_a = fa.spectral_centroid_hz or 0.0
    sc_b = fb.spectral_centroid_hz or 0.0
    vox_thr = settings.vocal_pitch_salience_threshold
    cent_thr = settings.recipe_vocal_spectral_centroid_hz_threshold
    if ps_a > vox_thr and ps_b > vox_thr and sc_a > cent_thr and sc_b > cent_thr:
        if score.overall > settings.recipe_vocal_overlap_overall_floor:
            return (
                NeuralMixCrossfaderFX.NEURAL_MIX_VOCAL_CUT,
                4,
                0.80,
                ["vocal overlap risk"],
            )
        return (
            NeuralMixCrossfaderFX.NEURAL_MIX_FADE,
            16,
            0.75,
            ["vocal overlap risk"],
        )

    # 8 Near-perfect match
    if (
        score.bpm > settings.recipe_perfect_bpm_floor
        and score.harmonic > settings.recipe_perfect_harmonic_floor
        and score.groove > settings.recipe_perfect_groove_floor
    ):
        if pair_type == SubgenrePairType.HARD_PAIR:
            return NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_CUT, 0, 0.95, []
        return NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP, 8, 0.92, []

    # 9 Graduated fallbacks
    if score.overall > settings.recipe_high_overall_floor:
        if (
            score.groove > settings.recipe_high_overall_groove_floor
            and score.bpm > settings.recipe_high_overall_bpm_floor
        ):
            return NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP, 16, 0.88, []
        return NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP, 8, 0.88, []
    if score.overall > settings.recipe_mid_overall_floor:
        if score.groove > settings.recipe_mid_overall_groove_floor and pair_type in (
            SubgenrePairType.HARD_PAIR,
            SubgenrePairType.HYPNOTIC_PAIR,
        ):
            return NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP, 16, 0.82, []
        return NeuralMixCrossfaderFX.NEURAL_MIX_FADE, 16, 0.80, []
    if score.overall > settings.recipe_low_overall_floor:
        return NeuralMixCrossfaderFX.NEURAL_MIX_FADE, 32, 0.72, []
    return NeuralMixCrossfaderFX.NEURAL_MIX_FADE, 16, 0.65, []


def rescue_hint(fx: NeuralMixCrossfaderFX) -> str:
    return _RESCUE.get(fx, "adjust blend length to taste")


def resolve_pair_type(
    fa: TrackFeatures,
    fb: TrackFeatures,
    mood_a: TechnoSubgenre | None,
    mood_b: TechnoSubgenre | None,
) -> SubgenrePairType:
    return classify_pair(
        mood_a or (fa.mood if fa.mood else None),
        mood_b or (fb.mood if fb.mood else None),
    )


def snap_bars_to_phrase(bars: int) -> int:
    """Snap bar count to musical phrase boundaries (4 / 8+ bars)."""
    if bars == 0:
        return 0
    if bars <= 4:
        return 4
    return max(8, round(bars / 8) * 8)


def clamp_pair_bars(bars: int, pair_type: SubgenrePairType) -> int:
    return clamp_bars(bars, pair_type)
