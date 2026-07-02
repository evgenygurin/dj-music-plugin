"""GeneticAlgorithm smoke test (small population, quick convergence)."""

from __future__ import annotations

from app.domain.optimization import GeneticAlgorithm
from app.domain.transition.scorer import TransitionScorer
from app.shared.features import TrackFeatures


def test_ga_returns_permutation() -> None:
    feats = [
        TrackFeatures(
            bpm=b,
            key_code=5,
            integrated_lufs=-8.0,
            energy_mean=0.3,
            spectral_centroid_hz=3000.0,
            onset_rate=5.0,
            kick_prominence=0.5,
            hnr_db=10.0,
            chroma_entropy=0.6,
        )
        for b in (124.0, 126.0, 128.0, 130.0)
    ]
    ids = [10, 20, 30, 40]
    ga = GeneticAlgorithm(
        scorer=TransitionScorer(),
        population_size=8,
        max_generations=5,
        mutation_rate=0.1,
        elitism_rate=0.25,
        tournament_size=2,
    )
    res = ga.optimize(feats, ids)
    assert sorted(res.track_order) == sorted(ids)
    assert 0.0 <= res.quality_score <= 1.0


def test_ga_reports_normalized_progress() -> None:
    feats = [
        TrackFeatures(
            bpm=b,
            key_code=5,
            integrated_lufs=-8.0,
            energy_mean=0.3,
            spectral_centroid_hz=3000.0,
            onset_rate=5.0,
            kick_prominence=0.5,
            hnr_db=10.0,
            chroma_entropy=0.6,
        )
        for b in (124.0, 126.0, 128.0, 130.0)
    ]
    events: list[tuple[int, float]] = []
    ga = GeneticAlgorithm(
        scorer=TransitionScorer(),
        population_size=8,
        max_generations=5,
        mutation_rate=0.1,
        elitism_rate=0.25,
        tournament_size=2,
    )

    ga.optimize(
        feats,
        [10, 20, 30, 40],
        on_progress=lambda progress, score: events.append((progress, score)),
    )

    assert events
    assert all(0 < progress <= 100 for progress, _ in events)
    assert events[-1][0] == 100
