"""Tests for TransitionRecipeEngine decision tree."""

from app.core.constants import SectionType, TechnoSubgenre
from app.entities.audio.features import TrackFeatures
from app.transition.recipe import DjayTransition, TransitionType
from app.transition.recipe_engine import TransitionRecipeEngine
from app.transition.score import TransitionScore
from app.transition.section_context import SectionContext

engine = TransitionRecipeEngine()


def _features(**kw) -> TrackFeatures:
    defaults = dict(
        bpm=130.0,
        key_code=15,
        integrated_lufs=-8.0,
        spectral_centroid_hz=2000.0,
        energy_mean=0.5,
        kick_prominence=0.5,
        onset_rate=4.0,
        hp_ratio=1.5,
        bpm_stability=0.9,
        bpm_confidence=0.8,
        pitch_salience_mean=0.2,
        mfcc_vector=[0.0] * 13,
    )
    defaults.update(kw)
    return TrackFeatures(**defaults)


FA = _features()
FB = _features()


def test_hard_reject_gives_filter_sweep():
    score = TransitionScore(hard_reject=True, reject_reason="BPM diff 14")
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type == TransitionType.FILTER_SWEEP
    assert recipe.bars == 16
    assert recipe.djay_transition == DjayTransition.FILTER
    assert recipe.confidence < 0.65


def test_drum_only_high_groove_gives_cut():
    score = TransitionScore(
        bpm=0.9, harmonic=0.8, energy=0.8, spectral=0.7, groove=0.85, timbral=0.7, overall=0.8
    )
    ctx = SectionContext(from_section=SectionType.OUTRO, to_section=SectionType.INTRO)
    recipe = engine.generate(score, FA, FB, section_context=ctx)
    assert recipe.transition_type == TransitionType.CUT
    assert recipe.bars == 0


def test_spectral_collision_gives_filter_sweep():
    score = TransitionScore(
        spectral=0.30, bpm=0.8, harmonic=0.7, energy=0.7, groove=0.6, timbral=0.6, overall=0.6
    )
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type == TransitionType.FILTER_SWEEP


def test_key_clash_compatible_drums_gives_neural_mix():
    score = TransitionScore(
        harmonic=0.40, groove=0.80, bpm=0.9, energy=0.7, spectral=0.6, timbral=0.6, overall=0.65
    )
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type == TransitionType.NEURAL_MIX_BLEND
    assert recipe.djay_transition == DjayTransition.NEURAL_MIX


def test_energy_gap_ramp_up_hard_gives_riser():
    score = TransitionScore(
        energy=0.30, bpm=0.9, harmonic=0.7, spectral=0.6, groove=0.6, timbral=0.6, overall=0.6
    )
    fa = _features(integrated_lufs=-10.0)
    fb = _features(integrated_lufs=-6.0)
    recipe = engine.generate(
        score,
        fa,
        fb,
        mood_a=TechnoSubgenre.HARD_TECHNO,
        mood_b=TechnoSubgenre.INDUSTRIAL,
    )
    assert recipe.transition_type == TransitionType.RISER


def test_ambient_pair_gives_dissolve():
    score = TransitionScore(
        bpm=0.9, harmonic=0.7, energy=0.7, spectral=0.6, groove=0.6, timbral=0.6, overall=0.7
    )
    recipe = engine.generate(
        score,
        FA,
        FB,
        mood_a=TechnoSubgenre.DUB_TECHNO,
        mood_b=TechnoSubgenre.AMBIENT_DUB,
    )
    assert recipe.transition_type == TransitionType.DISSOLVE
    assert recipe.bars >= 32


def test_hard_pair_high_score_gives_drop_swap():
    score = TransitionScore(
        bpm=0.9, harmonic=0.8, energy=0.8, spectral=0.7, groove=0.7, timbral=0.7, overall=0.75
    )
    recipe = engine.generate(
        score,
        FA,
        FB,
        mood_a=TechnoSubgenre.INDUSTRIAL,
        mood_b=TechnoSubgenre.HARD_TECHNO,
    )
    assert recipe.transition_type == TransitionType.DROP_SWAP
    assert recipe.bars <= 8


def test_vocal_conflict_gives_drop_swap_or_neural():
    score = TransitionScore(
        bpm=0.9, harmonic=0.8, energy=0.8, spectral=0.7, groove=0.7, timbral=0.7, overall=0.80
    )
    fa = _features(pitch_salience_mean=0.55, spectral_centroid_hz=3200)
    fb = _features(pitch_salience_mean=0.50, spectral_centroid_hz=2800)
    recipe = engine.generate(score, fa, fb)
    assert recipe.transition_type in {TransitionType.DROP_SWAP, TransitionType.NEURAL_MIX_BLEND}
    assert any("vocal" in w.lower() for w in recipe.warnings)


def test_perfect_match_gives_cut_or_bass_swap():
    score = TransitionScore(
        bpm=0.98,
        harmonic=0.90,
        energy=0.85,
        spectral=0.85,
        groove=0.80,
        timbral=0.80,
        overall=0.90,
    )
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type in {TransitionType.CUT, TransitionType.BASS_SWAP_SHORT}


def test_overall_080_gives_bass_swap_short():
    score = TransitionScore(
        bpm=0.8, harmonic=0.7, energy=0.7, spectral=0.6, groove=0.6, timbral=0.6, overall=0.82
    )
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type == TransitionType.BASS_SWAP_SHORT


def test_overall_065_gives_eq_blend():
    score = TransitionScore(
        bpm=0.7, harmonic=0.6, energy=0.6, spectral=0.6, groove=0.5, timbral=0.5, overall=0.68
    )
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type == TransitionType.EQ_BLEND


def test_overall_050_gives_bass_swap_long():
    score = TransitionScore(
        bpm=0.6, harmonic=0.6, energy=0.5, spectral=0.5, groove=0.5, timbral=0.5, overall=0.55
    )
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type == TransitionType.BASS_SWAP_LONG


def test_low_overall_gives_filter_sweep():
    score = TransitionScore(
        bpm=0.4, harmonic=0.6, energy=0.5, spectral=0.5, groove=0.4, timbral=0.4, overall=0.42
    )
    recipe = engine.generate(score, FA, FB)
    assert recipe.transition_type == TransitionType.FILTER_SWEEP


def test_phrase_snap_to_8():
    score = TransitionScore(
        bpm=0.8, harmonic=0.7, energy=0.7, spectral=0.6, groove=0.6, timbral=0.6, overall=0.82
    )
    recipe = engine.generate(score, FA, FB)
    assert recipe.bars % 8 == 0 or recipe.bars == 0


def test_recipe_has_steps():
    score = TransitionScore(
        bpm=0.8, harmonic=0.7, energy=0.7, spectral=0.6, groove=0.6, timbral=0.6, overall=0.82
    )
    recipe = engine.generate(score, FA, FB)
    assert len(recipe.steps) > 0
    assert all(isinstance(s.bar, int) for s in recipe.steps)
    assert all(s.deck in ("A", "B", "both") for s in recipe.steps)


def test_recipe_has_rescue_move():
    score = TransitionScore(
        bpm=0.8, harmonic=0.7, energy=0.7, spectral=0.6, groove=0.6, timbral=0.6, overall=0.82
    )
    recipe = engine.generate(score, FA, FB)
    assert recipe.rescue_move
    assert len(recipe.rescue_move) > 5


def test_recipe_confidence_in_range():
    score = TransitionScore(
        bpm=0.8, harmonic=0.7, energy=0.7, spectral=0.6, groove=0.6, timbral=0.6, overall=0.82
    )
    recipe = engine.generate(score, FA, FB)
    assert 0.0 <= recipe.confidence <= 1.0
