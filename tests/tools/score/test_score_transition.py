"""Task 2: ScoringWeights + S = Σ w·S."""

from __future__ import annotations


def test_scoring_weights_sum_to_one() -> None:
    from app.schemas.scoring import ScoringWeights

    w = ScoringWeights(
        w_harmony=0.3, w_rhythmic=0.25, w_timbral=0.2, w_energy=0.15, w_structure=0.1
    )
    assert (
        abs(sum([w.w_harmony, w.w_rhythmic, w.w_timbral, w.w_energy, w.w_structure]) - 1.0) < 1e-6
    )
    # validation
    import pytest

    with pytest.raises(Exception):
        ScoringWeights(w_harmony=2.0)  # type: ignore[call-arg]


def test_scoring_weights_defaults_sum_to_one() -> None:
    from app.schemas.scoring import ScoringWeights

    w = ScoringWeights()
    total = w.w_harmony + w.w_rhythmic + w.w_timbral + w.w_energy + w.w_structure
    assert abs(total - 1.0) < 1e-6
    assert w.roughness_vs_camelot == 0.5


def test_scoring_weights_normalized() -> None:
    from app.schemas.scoring import ScoringWeights

    w = ScoringWeights(
        w_harmony=0.3, w_rhythmic=0.25, w_timbral=0.2, w_energy=0.15, w_structure=0.1
    )
    norm = w.normalized()
    assert abs(sum(norm.values()) - 1.0) < 1e-9
    assert norm["w_harmony"] == w.w_harmony  # already sum 1
    # non-unit sum -> normalized
    w2 = ScoringWeights.model_construct(
        w_harmony=0.5,
        w_rhythmic=0.5,
        w_timbral=0.5,
        w_energy=0.5,
        w_structure=0.5,
        roughness_vs_camelot=0.5,
    )
    norm2 = w2.normalized()
    assert abs(sum(norm2.values()) - 1.0) < 1e-9
    assert norm2["w_harmony"] == 0.2


def test_scoring_weights_field_validation() -> None:
    import pytest

    from app.schemas.scoring import ScoringWeights

    with pytest.raises(Exception):
        ScoringWeights(w_rhythmic=-0.1)  # type: ignore[call-arg]
    with pytest.raises(Exception):
        ScoringWeights(w_timbral=1.5)  # type: ignore[call-arg]
    with pytest.raises(Exception):
        ScoringWeights(roughness_vs_camelot=2.0)  # type: ignore[call-arg]
    # extra fields forbidden
    with pytest.raises(Exception):
        ScoringWeights(extra=1.0)  # type: ignore[call-arg]


def test_score_harmonic_pure_alpha_blend() -> None:
    from app.shared.features import TrackFeatures
    from app.tools.score.score_harmonic import score_harmonic_pure

    # два трека: одинаковый ключ (dist 0 -> score 1.0), разная roughness
    a = TrackFeatures(key_code=0, dissonance_mean=0.2, key_confidence=1.0)
    b = TrackFeatures(key_code=0, dissonance_mean=0.2, key_confidence=1.0)
    # alpha=1 -> только Camelot (1.0), alpha=0 -> только roughness (0.8)
    r1 = score_harmonic_pure(a, b, alpha=1.0)
    assert r1.key_distance == 0
    assert r1.key_score == 1.0
    assert r1.roughness == 0.2
    assert r1.roughness_score == 0.8
    assert r1.S_h == 1.0

    r0 = score_harmonic_pure(a, b, alpha=0.0)
    assert r0.S_h == 0.8

    r05 = score_harmonic_pure(a, b, alpha=0.5)
    assert abs(r05.S_h - 0.9) < 1e-9  # 0.5*1.0 + 0.5*0.8


def test_score_harmonic_pure_key_distance() -> None:
    from app.shared.features import TrackFeatures
    from app.tools.score.score_harmonic import score_harmonic_pure

    # 0 vs 12: wheel pos 1 vs 7 -> dist 6? plus mode same -> 6
    # CAMELOT_HARMONIC_BASE 6->0.0, roughness 0.5 neutral
    a = TrackFeatures(key_code=0, dissonance_mean=0.5, key_confidence=1.0)
    b = TrackFeatures(key_code=12, dissonance_mean=0.5, key_confidence=1.0)
    r = score_harmonic_pure(a, b, alpha=1.0)
    # key_score should be small (0.0 for dist>=5)
    assert r.key_score == 0.0
    assert r.S_h == 0.0
    # при alpha 0 — S_h = roughness_score 0.5
    r2 = score_harmonic_pure(a, b, alpha=0.0)
    assert r2.S_h == 0.5


def test_score_harmonic_pure_atonal_fallback() -> None:
    from app.shared.features import TrackFeatures
    from app.tools.score.score_harmonic import score_harmonic_pure

    a = TrackFeatures(key_code=0, atonality=True, dissonance_mean=0.3)
    b = TrackFeatures(key_code=0, dissonance_mean=0.3)
    r = score_harmonic_pure(a, b, alpha=1.0)
    # atonal -> key_score 0.5 fallback, not 1.0
    assert r.key_distance is None
    assert r.key_score == 0.5


def test_score_transition_pure_weighted_sum() -> None:
    from app.schemas.scoring import ScoringWeights
    from app.shared.features import TrackFeatures
    from app.tools.score.score_harmonic import score_transition_pure

    a = TrackFeatures(
        bpm=128.0,
        key_code=0,
        key_confidence=1.0,
        dissonance_mean=0.2,
        integrated_lufs=-10.0,
        mfcc_vector=[1.0, 0.0],
        spectral_contrast=5.0,
        dominant_phrase_bars=16,
    )
    b = TrackFeatures(
        bpm=128.0,
        key_code=0,
        key_confidence=1.0,
        dissonance_mean=0.2,
        integrated_lufs=-10.0,
        mfcc_vector=[1.0, 0.0],
        spectral_contrast=5.0,
        dominant_phrase_bars=16,
    )
    w = ScoringWeights(
        w_harmony=0.3, w_rhythmic=0.25, w_timbral=0.2, w_energy=0.15, w_structure=0.1
    )
    res = score_transition_pure(a, b, w)
    # все компоненты ~1.0 (идентичные треки) => overall ~1.0
    assert res.S_harmony == 1.0 or abs(res.S_harmony - 0.9) < 0.2  # S_h 0.9 (alpha 0.5)
    assert 0.8 <= res.overall <= 1.0
    # S = Σ w·S: проверим формулу вручную
    norm = w.normalized()
    expected = (
        norm["w_harmony"] * res.S_harmony
        + norm["w_rhythmic"] * res.S_rhythmic
        + norm["w_timbral"] * res.S_timbral
        + norm["w_energy"] * res.S_energy
        + norm["w_structure"] * res.S_structure
    )
    assert abs(res.overall - expected) < 1e-9


def test_score_transition_pure_normalized_weights() -> None:
    from app.schemas.scoring import ScoringWeights
    from app.shared.features import TrackFeatures
    from app.tools.score.score_harmonic import score_transition_pure

    a = TrackFeatures(bpm=128.0, integrated_lufs=-10.0)
    b = TrackFeatures(bpm=130.0, integrated_lufs=-9.0)
    # не-нормализованные веса (сумма 2.5) — через model_construct обходим валидацию
    w_raw = ScoringWeights.model_construct(
        w_harmony=0.5,
        w_rhythmic=0.5,
        w_timbral=0.5,
        w_energy=0.5,
        w_structure=0.5,
        roughness_vs_camelot=0.5,
    )
    res = score_transition_pure(a, b, w_raw)
    # normalized должны дать по 0.2 каждому
    norm = w_raw.normalized()
    assert all(abs(v - 0.2) < 1e-9 for v in norm.values())
    assert 0.0 <= res.overall <= 1.0


def test_schemas_harmonic_profile_and_score_result() -> None:
    from app.schemas.scoring import HarmonicProfile, ScoreResult, ScoringWeights

    hp = HarmonicProfile(track_id=1, roughness=0.3)
    assert hp.track_id == 1
    sr = ScoreResult(
        a_id=1,
        b_id=2,
        S_harmony=0.9,
        S_rhythmic=0.8,
        S_timbral=0.7,
        S_energy=0.85,
        S_structure=0.9,
        overall=0.83,
        weights=ScoringWeights(),
    )
    assert sr.overall == 0.83
