"""Tests for P3 scoring enrichments — full feature utilization."""

from __future__ import annotations

from app.entities.audio.features import TrackFeatures
from app.transition.scorer import TransitionScorer


def _base(**overrides: object) -> TrackFeatures:
    """Minimal valid features for scoring (no hard reject)."""
    defaults: dict[str, object] = {
        "bpm": 130.0,
        "key_code": 0,
        "integrated_lufs": -8.0,
        "spectral_centroid_hz": 2000.0,
        "spectral_flatness": 0.2,
        "energy_mean": 0.5,
        "onset_rate": 4.0,
        "kick_prominence": 0.5,
        "hnr_db": 5.0,
        "chroma_entropy": 3.0,
        "mfcc_vector": [0.1] * 13,
        "energy_bands": [0.1, 0.2, 0.15, 0.15, 0.1, 0.05],
    }
    defaults.update(overrides)
    return TrackFeatures(**defaults)  # type: ignore[arg-type]


# ── BPM confidence ────────────────────────────────────


class TestBpmConfidence:
    def test_low_confidence_reduces_bpm_score(self) -> None:
        scorer = TransitionScorer()
        a_high = _base(bpm_confidence=0.95)
        b_high = _base(bpm_confidence=0.95, bpm=131.0)
        score_high = scorer.score(a_high, b_high)

        a_low = _base(bpm_confidence=0.3)
        b_low = _base(bpm_confidence=0.3, bpm=131.0)
        score_low = scorer.score(a_low, b_low)

        assert score_high.bpm > score_low.bpm

    def test_none_confidence_no_penalty(self) -> None:
        scorer = TransitionScorer()
        a = _base(bpm_confidence=None)
        b = _base(bpm_confidence=None)
        result = scorer.score(a, b)
        assert result.bpm > 0.9


class TestVariableTempo:
    def test_variable_tempo_penalizes(self) -> None:
        scorer = TransitionScorer()
        a_var = _base(variable_tempo=True)
        b_var = _base(variable_tempo=False)
        score_var = scorer.score(a_var, b_var)

        a_fixed = _base(variable_tempo=False)
        b_fixed = _base(variable_tempo=False)
        score_fixed = scorer.score(a_fixed, b_fixed)

        assert score_fixed.bpm > score_var.bpm

    def test_none_variable_tempo_no_penalty(self) -> None:
        scorer = TransitionScorer()
        a = _base(variable_tempo=None)
        b = _base(variable_tempo=None)
        result = scorer.score(a, b)
        assert result.bpm > 0.9


# ── Harmonic enrichment ───────────────────────────────


class TestAtonalityEnrichment:
    def test_both_atonal_relaxes_harmonic(self) -> None:
        scorer = TransitionScorer()
        a = _base(key_code=0, atonality=True)
        b = _base(key_code=8, atonality=True)  # distance=4
        score_atonal = scorer.score(a, b)

        a_tonal = _base(key_code=0, atonality=False)
        b_tonal = _base(key_code=8, atonality=False)
        score_tonal = scorer.score(a_tonal, b_tonal)

        assert score_atonal.harmonic > score_tonal.harmonic

    def test_one_atonal_no_relaxation(self) -> None:
        scorer = TransitionScorer()
        a = _base(key_code=0, atonality=True)
        b = _base(key_code=8, atonality=False)
        score_mixed = scorer.score(a, b)

        a_both = _base(key_code=0, atonality=False)
        b_both = _base(key_code=8, atonality=False)
        score_tonal = scorer.score(a_both, b_both)

        assert abs(score_mixed.harmonic - score_tonal.harmonic) < 0.15


class TestKeyConfidenceEnrichment:
    def test_low_key_confidence_relaxes(self) -> None:
        scorer = TransitionScorer()
        a = _base(key_code=0, key_confidence=0.3)
        b = _base(key_code=6, key_confidence=0.3)
        score_low = scorer.score(a, b)

        a_high = _base(key_code=0, key_confidence=0.9)
        b_high = _base(key_code=6, key_confidence=0.9)
        score_high = scorer.score(a_high, b_high)

        assert score_low.harmonic >= score_high.harmonic

    def test_none_key_confidence_no_change(self) -> None:
        scorer = TransitionScorer()
        a = _base(key_confidence=None)
        b = _base(key_confidence=None)
        result = scorer.score(a, b)
        assert 0.0 <= result.harmonic <= 1.0


# ── Energy enrichment ─────────────────────────────────


class TestEnergyEnrichment:
    def test_lra_diff_penalizes(self) -> None:
        scorer = TransitionScorer()
        a = _base(loudness_range_lu=4.0)
        b = _base(loudness_range_lu=14.0)  # diff=10 > 8
        score_diff = scorer.score(a, b)

        a_sim = _base(loudness_range_lu=5.0)
        b_sim = _base(loudness_range_lu=6.0)
        score_sim = scorer.score(a_sim, b_sim)

        assert score_sim.energy >= score_diff.energy

    def test_crest_diff_penalizes(self) -> None:
        scorer = TransitionScorer()
        a = _base(crest_factor_db=5.0)
        b = _base(crest_factor_db=18.0)  # diff=13 > 10
        score_diff = scorer.score(a, b)

        a_sim = _base(crest_factor_db=10.0)
        b_sim = _base(crest_factor_db=11.0)
        score_sim = scorer.score(a_sim, b_sim)

        assert score_sim.energy >= score_diff.energy

    def test_same_energy_slope_bonus(self) -> None:
        scorer = TransitionScorer()
        a_up = _base(energy_slope=0.05)
        b_up = _base(energy_slope=0.03)
        score_same = scorer.score(a_up, b_up)

        a_up2 = _base(energy_slope=0.05)
        b_down = _base(energy_slope=-0.05)
        score_opp = scorer.score(a_up2, b_down)

        assert score_same.energy >= score_opp.energy

    def test_none_energy_extras_no_change(self) -> None:
        scorer = TransitionScorer()
        a = _base(loudness_range_lu=None, crest_factor_db=None, energy_slope=None)
        b = _base(loudness_range_lu=None, crest_factor_db=None, energy_slope=None)
        result = scorer.score(a, b)
        assert 0.0 <= result.energy <= 1.0


# ── Spectral enrichment ───────────────────────────────


class TestSpectralEnrichment:
    def test_similar_rolloff_boosts(self) -> None:
        scorer = TransitionScorer()
        a = _base(spectral_rolloff_85=4000.0, spectral_rolloff_95=8000.0)
        b = _base(spectral_rolloff_85=4100.0, spectral_rolloff_95=8100.0)
        score_sim = scorer.score(a, b)

        a_diff = _base(spectral_rolloff_85=2000.0, spectral_rolloff_95=4000.0)
        b_diff = _base(spectral_rolloff_85=8000.0, spectral_rolloff_95=16000.0)
        score_diff = scorer.score(a_diff, b_diff)

        assert score_sim.spectral >= score_diff.spectral

    def test_similar_slope_boosts(self) -> None:
        scorer = TransitionScorer()
        a = _base(spectral_slope=-0.003)
        b = _base(spectral_slope=-0.004)
        score_sim = scorer.score(a, b)

        a_diff = _base(spectral_slope=-0.001)
        b_diff = _base(spectral_slope=-0.01)
        score_diff = scorer.score(a_diff, b_diff)

        assert score_sim.spectral >= score_diff.spectral

    def test_none_spectral_extras_graceful(self) -> None:
        scorer = TransitionScorer()
        a = _base(spectral_rolloff_85=None, spectral_slope=None, spectral_flux_std=None)
        b = _base(spectral_rolloff_85=None, spectral_slope=None, spectral_flux_std=None)
        result = scorer.score(a, b)
        assert 0.0 <= result.spectral <= 1.0


# ── Groove enrichment ─────────────────────────────────


class TestGrooveEnrichment:
    def test_pulse_clarity_similarity(self) -> None:
        scorer = TransitionScorer()
        a = _base(pulse_clarity=0.9)
        b = _base(pulse_clarity=0.85)
        score_sim = scorer.score(a, b)

        a_diff = _base(pulse_clarity=0.9)
        b_diff = _base(pulse_clarity=0.2)
        score_diff = scorer.score(a_diff, b_diff)

        assert score_sim.groove >= score_diff.groove

    def test_hp_ratio_similarity(self) -> None:
        scorer = TransitionScorer()
        a = _base(hp_ratio=2.0)
        b = _base(hp_ratio=2.2)
        score_sim = scorer.score(a, b)

        a_diff = _base(hp_ratio=1.0)
        b_diff = _base(hp_ratio=7.0)
        score_diff = scorer.score(a_diff, b_diff)

        assert score_sim.groove >= score_diff.groove

    def test_tempogram_similarity(self) -> None:
        scorer = TransitionScorer()
        vec = [0.8, 0.1, 0.05, 0.05]
        a = _base(tempogram_ratio_vector=vec)
        b = _base(tempogram_ratio_vector=vec)
        score_sim = scorer.score(a, b)

        a_diff = _base(tempogram_ratio_vector=[0.9, 0.05, 0.025, 0.025])
        b_diff = _base(tempogram_ratio_vector=[0.1, 0.5, 0.2, 0.2])
        score_diff = scorer.score(a_diff, b_diff)

        assert score_sim.groove >= score_diff.groove

    def test_none_groove_extras_graceful(self) -> None:
        scorer = TransitionScorer()
        a = _base(pulse_clarity=None, hp_ratio=None, tempogram_ratio_vector=None)
        b = _base(pulse_clarity=None, hp_ratio=None, tempogram_ratio_vector=None)
        result = scorer.score(a, b)
        assert 0.0 <= result.groove <= 1.0


# ── Timbral enrichment ────────────────────────────────


class TestTimbralEnrichment:
    def test_danceability_similarity(self) -> None:
        scorer = TransitionScorer()
        a = _base(spectral_contrast=5.0, pitch_salience_mean=0.3, danceability=1.5)
        b = _base(spectral_contrast=5.0, pitch_salience_mean=0.3, danceability=1.4)
        score_sim = scorer.score(a, b)

        a_diff = _base(spectral_contrast=5.0, pitch_salience_mean=0.3, danceability=0.5)
        b_diff = _base(spectral_contrast=5.0, pitch_salience_mean=0.3, danceability=2.5)
        score_diff = scorer.score(a_diff, b_diff)

        assert score_sim.timbral >= score_diff.timbral

    def test_dynamic_complexity_similarity(self) -> None:
        scorer = TransitionScorer()
        a = _base(spectral_contrast=5.0, pitch_salience_mean=0.3, dynamic_complexity=4.0)
        b = _base(spectral_contrast=5.0, pitch_salience_mean=0.3, dynamic_complexity=4.2)
        score_sim = scorer.score(a, b)

        a_diff = _base(spectral_contrast=5.0, pitch_salience_mean=0.3, dynamic_complexity=1.0)
        b_diff = _base(spectral_contrast=5.0, pitch_salience_mean=0.3, dynamic_complexity=9.0)
        score_diff = scorer.score(a_diff, b_diff)

        assert score_sim.timbral >= score_diff.timbral

    def test_none_timbral_extras_graceful(self) -> None:
        scorer = TransitionScorer()
        a = _base(
            danceability=None,
            dynamic_complexity=None,
            spectral_contrast=5.0,
            pitch_salience_mean=0.3,
        )
        b = _base(
            danceability=None,
            dynamic_complexity=None,
            spectral_contrast=5.0,
            pitch_salience_mean=0.3,
        )
        result = scorer.score(a, b)
        assert result.timbral > 0.9


# ── Backward compat ───────────────────────────────────


class TestP3BackwardCompat:
    def test_all_none_still_neutral(self) -> None:
        scorer = TransitionScorer()
        a = TrackFeatures()
        b = TrackFeatures()
        result = scorer.score(a, b)
        assert not result.hard_reject
        assert abs(result.overall - 0.5) < 0.15

    def test_scores_valid_range(self) -> None:
        scorer = TransitionScorer()
        a = _base()
        b = _base(bpm=132.0, key_code=1, integrated_lufs=-9.0)
        result = scorer.score(a, b)
        assert 0.0 <= result.overall <= 1.0
        assert 0.0 <= result.bpm <= 1.0
        assert 0.0 <= result.harmonic <= 1.0
        assert 0.0 <= result.energy <= 1.0
        assert 0.0 <= result.spectral <= 1.0
        assert 0.0 <= result.groove <= 1.0
        assert 0.0 <= result.timbral <= 1.0
