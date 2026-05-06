"""Tests for NeuralMixScorer — stem-aware Neural Mix transition scoring."""

from __future__ import annotations

import pytest

from app.domain.transition.neural_mix import (
    NEURAL_MIX_STEMS,
    TRANSITION_ENERGY_BIAS,
    TRANSITION_STEM_WEIGHTS,
    TRANSITION_TYPES,
    NeuralMixScore,
    NeuralMixScorer,
    NeuralMixStem,
    NeuralMixTransition,
    score_bass_compat,
    score_drums_compat,
    score_harmonic_compat,
    score_vocal_compat,
)
from app.shared.features import TrackFeatures


@pytest.fixture
def scorer() -> NeuralMixScorer:
    return NeuralMixScorer()


def _make_track(**kwargs: object) -> TrackFeatures:
    defaults: dict[str, object] = {
        "bpm": 128.0,
        "key_code": 14,  # 8A
        "integrated_lufs": -8.0,
        "spectral_centroid_hz": 3000.0,
        "spectral_flatness": 0.1,
        "energy_mean": 0.6,
        "onset_rate": 4.0,
        "kick_prominence": 0.5,
        "hnr_db": 5.0,
        "chroma_entropy": 2.5,
        "mfcc_vector": [0.1] * 13,
        "energy_bands": [0.20, 0.20, 0.15, 0.15, 0.15, 0.15],
    }
    defaults.update(kwargs)
    return TrackFeatures(**defaults)  # type: ignore[arg-type]


# ── Enum and weight table constants ─────────────────────


class TestEnumsAndWeights:
    def test_four_stems(self) -> None:
        assert len(NeuralMixStem) == 4
        assert set(NeuralMixStem) == {
            NeuralMixStem.DRUMS,
            NeuralMixStem.BASS,
            NeuralMixStem.HARMONICS,
            NeuralMixStem.VOCALS,
        }
        assert len(NEURAL_MIX_STEMS) == 4

    def test_seven_transition_types_exact(self) -> None:
        assert len(NeuralMixTransition) == 7
        assert set(NeuralMixTransition) == {
            NeuralMixTransition.FADE,
            NeuralMixTransition.ECHO_OUT,
            NeuralMixTransition.VOCAL_SUSTAIN,
            NeuralMixTransition.HARMONIC_SUSTAIN,
            NeuralMixTransition.DRUM_SWAP,
            NeuralMixTransition.VOCAL_CUT,
            NeuralMixTransition.DRUM_CUT,
        }
        assert len(TRANSITION_TYPES) == 7

    def test_every_transition_has_stem_weights_summing_to_one(self) -> None:
        for transition, weights in TRANSITION_STEM_WEIGHTS.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.001, f"{transition}: weights sum to {total}"
            assert set(weights.keys()) == set(NeuralMixStem)

    def test_every_transition_has_energy_bias(self) -> None:
        for transition in NeuralMixTransition:
            assert transition in TRANSITION_ENERGY_BIAS
            assert -1.0 <= TRANSITION_ENERGY_BIAS[transition] <= 1.0

    def test_drum_cut_prefers_ramp_up(self) -> None:
        # Drop-style breakdown into slam expects a louder incoming track.
        assert TRANSITION_ENERGY_BIAS[NeuralMixTransition.DRUM_CUT] > 0

    def test_echo_out_prefers_cool_down(self) -> None:
        # Echo tail = gentle wind-down.
        assert TRANSITION_ENERGY_BIAS[NeuralMixTransition.ECHO_OUT] < 0

    def test_fade_neutral(self) -> None:
        assert TRANSITION_ENERGY_BIAS[NeuralMixTransition.FADE] == 0.0

    def test_vocal_sustain_dominant_on_vocals_stem(self) -> None:
        weights = TRANSITION_STEM_WEIGHTS[NeuralMixTransition.VOCAL_SUSTAIN]
        assert weights[NeuralMixStem.VOCALS] >= max(
            weights[NeuralMixStem.DRUMS],
            weights[NeuralMixStem.BASS],
            weights[NeuralMixStem.HARMONICS],
        )

    def test_drum_swap_dominant_on_drums_stem(self) -> None:
        weights = TRANSITION_STEM_WEIGHTS[NeuralMixTransition.DRUM_SWAP]
        assert weights[NeuralMixStem.DRUMS] >= weights[NeuralMixStem.HARMONICS]
        assert weights[NeuralMixStem.DRUMS] >= weights[NeuralMixStem.VOCALS]

    def test_harmonic_sustain_dominant_on_harmonics_stem(self) -> None:
        weights = TRANSITION_STEM_WEIGHTS[NeuralMixTransition.HARMONIC_SUSTAIN]
        assert weights[NeuralMixStem.HARMONICS] == max(weights.values())


# ── Hard constraints (shared with TransitionScorer) ─────


class TestHardConstraints:
    def test_hard_reject_bpm(self, scorer: NeuralMixScorer) -> None:
        a = _make_track(bpm=128.0)
        b = _make_track(bpm=142.0)  # diff = 14 > 10
        result = scorer.score(a, b)
        assert result.hard_reject is True
        assert result.overall == 0.0
        assert result.reject_reason is not None

    def test_hard_reject_camelot(self, scorer: NeuralMixScorer) -> None:
        a = _make_track(key_code=0)
        b = _make_track(key_code=12)  # distance = 6
        result = scorer.score(a, b)
        assert result.hard_reject is True

    def test_hard_reject_energy(self, scorer: NeuralMixScorer) -> None:
        a = _make_track(integrated_lufs=-6.0)
        b = _make_track(integrated_lufs=-14.0)  # gap = 8 > 6
        result = scorer.score(a, b)
        assert result.hard_reject is True

    def test_no_hard_reject_within_limits(self, scorer: NeuralMixScorer) -> None:
        a = _make_track(bpm=128.0, key_code=14, integrated_lufs=-8.0)
        b = _make_track(bpm=130.0, key_code=12, integrated_lufs=-9.0)
        result = scorer.score(a, b)
        assert result.hard_reject is False
        assert result.overall > 0.0


# ── Stem compatibility scores ───────────────────────────


class TestStemScores:
    def test_stem_scores_populated(self, scorer: NeuralMixScorer) -> None:
        result = scorer.score(_make_track(), _make_track())
        for stem in NeuralMixStem:
            assert stem in result.stem_scores
            assert 0.0 <= result.stem_scores[stem] <= 1.0

    def test_drums_compat_high_for_matched_bpm(self) -> None:
        a = _make_track(bpm=128.0, kick_prominence=0.5, onset_rate=4.0)
        b = _make_track(bpm=128.0, kick_prominence=0.5, onset_rate=4.0)
        assert score_drums_compat(a, b) > 0.9

    def test_drums_compat_lower_for_bpm_mismatch(self) -> None:
        a = _make_track(bpm=128.0)
        b = _make_track(bpm=134.0)
        assert score_drums_compat(a, b) < 0.6

    def test_bass_compat_high_for_same_key(self) -> None:
        assert score_bass_compat(_make_track(key_code=14), _make_track(key_code=14)) > 0.85

    def test_bass_compat_low_for_key_clash(self) -> None:
        a = _make_track(key_code=14)  # 8A
        b = _make_track(key_code=6)  # 4A — distance=4
        assert score_bass_compat(a, b) < 0.4

    def test_harmonic_compat_respects_hnr(self) -> None:
        strong = score_harmonic_compat(_make_track(hnr_db=10.0), _make_track(hnr_db=10.0))
        weak = score_harmonic_compat(_make_track(hnr_db=-25.0), _make_track(hnr_db=-25.0))
        assert strong >= weak

    def test_vocal_compat_high_when_centroid_matches(self) -> None:
        a = _make_track(spectral_centroid_hz=3000.0, chroma_entropy=2.5)
        b = _make_track(spectral_centroid_hz=3000.0, chroma_entropy=2.5)
        assert score_vocal_compat(a, b) > 0.9


# ── Per-transition scores ───────────────────────────────


class TestTransitionScores:
    def test_all_seven_transition_scores_populated(self, scorer: NeuralMixScorer) -> None:
        result = scorer.score(_make_track(), _make_track())
        assert len(result.transition_scores) == 7
        for transition in NeuralMixTransition:
            assert transition in result.transition_scores
            assert 0.0 <= result.transition_scores[transition] <= 1.0

    def test_best_transition_is_max_score(self, scorer: NeuralMixScorer) -> None:
        result = scorer.score(_make_track(), _make_track())
        assert result.best_transition is not None
        top = max(result.transition_scores.values())
        assert result.transition_scores[result.best_transition] == pytest.approx(top)
        assert result.overall == pytest.approx(top)

    def test_drum_cut_rewards_energy_ramp_up(self, scorer: NeuralMixScorer) -> None:
        up = scorer.score(
            _make_track(integrated_lufs=-12.0),
            _make_track(integrated_lufs=-8.0),  # +4 LUFS ramp up
        )
        down = scorer.score(
            _make_track(integrated_lufs=-8.0),
            _make_track(integrated_lufs=-12.0),  # -4 LUFS ramp down
        )
        assert (
            up.transition_scores[NeuralMixTransition.DRUM_CUT]
            > down.transition_scores[NeuralMixTransition.DRUM_CUT]
        )

    def test_echo_out_prefers_cool_down(self, scorer: NeuralMixScorer) -> None:
        up = scorer.score(
            _make_track(integrated_lufs=-12.0),
            _make_track(integrated_lufs=-8.0),
        )
        down = scorer.score(
            _make_track(integrated_lufs=-8.0),
            _make_track(integrated_lufs=-12.0),
        )
        assert (
            down.transition_scores[NeuralMixTransition.ECHO_OUT]
            >= up.transition_scores[NeuralMixTransition.ECHO_OUT]
        )

    def test_fade_score_on_matching_tracks(self, scorer: NeuralMixScorer) -> None:
        result = scorer.score(_make_track(), _make_track())
        assert result.transition_scores[NeuralMixTransition.FADE] > 0.7


# ── Overall / missing features ──────────────────────────


class TestOverall:
    def test_overall_between_0_and_1(self, scorer: NeuralMixScorer) -> None:
        result = scorer.score(_make_track(), _make_track(bpm=130.0, key_code=16))
        assert 0.0 <= result.overall <= 1.0

    def test_identical_tracks_high_score(self, scorer: NeuralMixScorer) -> None:
        result = scorer.score(_make_track(), _make_track())
        assert result.overall > 0.7

    def test_missing_features_neutral(self, scorer: NeuralMixScorer) -> None:
        a = TrackFeatures()
        b = TrackFeatures()
        result = scorer.score(a, b)
        assert not result.hard_reject
        assert 0.3 <= result.overall <= 0.7

    def test_score_returns_neural_mix_dataclass(self, scorer: NeuralMixScorer) -> None:
        result = scorer.score(_make_track(), _make_track())
        assert isinstance(result, NeuralMixScore)


# ── score_with_candidates parity ────────────────────────


class TestScoreWithCandidates:
    def test_no_candidate_data_falls_back(self, scorer: NeuralMixScorer) -> None:
        a = _make_track()
        b = _make_track(bpm=130.0)
        normal = scorer.score(a, b)
        with_c = scorer.score_with_candidates(a, b)
        assert normal.overall == pytest.approx(with_c.overall)
        assert normal.best_transition == with_c.best_transition

    def test_candidate_bpm_hard_reject(self, scorer: NeuralMixScorer) -> None:
        result = scorer.score_with_candidates(
            _make_track(), _make_track(), candidate_bpm_distance=15.0
        )
        assert result.hard_reject is True

    def test_candidate_key_hard_reject(self, scorer: NeuralMixScorer) -> None:
        result = scorer.score_with_candidates(
            _make_track(), _make_track(), candidate_key_distance=5
        )
        assert result.hard_reject is True

    def test_candidate_energy_hard_reject(self, scorer: NeuralMixScorer) -> None:
        result = scorer.score_with_candidates(
            _make_track(), _make_track(), candidate_energy_delta=7.0
        )
        assert result.hard_reject is True
