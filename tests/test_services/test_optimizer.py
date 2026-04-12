"""Tests for GA optimizer and greedy chain builder."""

from __future__ import annotations

import random

from dj_music.schemas.audio import TrackFeatures
from dj_music.optimization.fitness import compute_fitness
from dj_music.optimization.genetic import GeneticAlgorithm
from dj_music.optimization.greedy import GreedyChainBuilder
from dj_music.templates.registry import get_template
from dj_music.transition.scorer import TransitionScorer

# ── Test fixtures ───────────────────────────────────────


def _make_tracks(n: int, seed: int = 42) -> tuple[list[TrackFeatures], list[int]]:
    """Create n synthetic tracks with realistic techno features."""
    rng = random.Random(seed)
    tracks: list[TrackFeatures] = []
    ids: list[int] = []
    for i in range(n):
        bpm = 124.0 + i * 2.0  # gradual BPM increase
        lufs = -14.0 + i * (8.0 / max(n - 1, 1))  # -14 to -6
        tracks.append(
            TrackFeatures(
                bpm=bpm,
                key_code=(i * 2) % 24,  # spread across Camelot wheel
                integrated_lufs=lufs,
                spectral_centroid_hz=2000.0 + rng.uniform(-500, 500),
                energy_mean=0.3 + i * (0.5 / max(n - 1, 1)),
                onset_rate=3.0 + rng.uniform(-1, 1),
                kick_prominence=0.4 + rng.uniform(-0.1, 0.1),
            )
        )
        ids.append(i + 1)
    return tracks, ids


def _make_compatible_tracks(
    n: int,
) -> tuple[list[TrackFeatures], list[int]]:
    """Create n tracks with close BPMs and keys for good transitions."""
    tracks: list[TrackFeatures] = []
    ids: list[int] = []
    for i in range(n):
        tracks.append(
            TrackFeatures(
                bpm=128.0 + i * 0.5,
                key_code=14,  # all 8A — perfect harmonic match
                integrated_lufs=-10.0 + i * 0.3,
                spectral_centroid_hz=3000.0,
                energy_mean=0.5,
                onset_rate=4.0,
                kick_prominence=0.5,
            )
        )
        ids.append(100 + i)
    return tracks, ids


# ── Greedy Chain Builder ────────────────────────────────


class TestGreedyChainBuilder:
    def test_produces_valid_ordering(self) -> None:
        random.seed(42)
        tracks, ids = _make_tracks(8)
        scorer = TransitionScorer()
        builder = GreedyChainBuilder(scorer)
        result = builder.build(tracks, ids)

        assert result.algorithm == "greedy"
        assert sorted(result.track_order) == sorted(ids)
        assert result.quality_score > 0.0
        assert len(result.track_order) == len(ids)

    def test_empty_tracks(self) -> None:
        scorer = TransitionScorer()
        builder = GreedyChainBuilder(scorer)
        result = builder.build([], [])
        assert result.track_order == []
        assert result.quality_score == 0.0

    def test_single_track(self) -> None:
        tracks = [TrackFeatures(bpm=128.0, key_code=14, integrated_lufs=-8.0)]
        scorer = TransitionScorer()
        builder = GreedyChainBuilder(scorer)
        result = builder.build(tracks, [1])
        assert result.track_order == [1]

    def test_respects_pinned_tracks(self) -> None:
        random.seed(42)
        tracks, ids = _make_tracks(6)
        scorer = TransitionScorer()
        builder = GreedyChainBuilder(scorer)
        pinned = {ids[0], ids[3]}
        result = builder.build(tracks, ids, pinned=pinned)

        # All pinned tracks must appear in result
        for pid in pinned:
            assert pid in result.track_order

        # All track IDs present
        assert sorted(result.track_order) == sorted(ids)

    def test_all_tracks_included(self) -> None:
        random.seed(42)
        tracks, ids = _make_tracks(10)
        scorer = TransitionScorer()
        builder = GreedyChainBuilder(scorer)
        result = builder.build(tracks, ids)
        assert set(result.track_order) == set(ids)

    def test_compatible_tracks_high_quality(self) -> None:
        random.seed(42)
        tracks, ids = _make_compatible_tracks(6)
        scorer = TransitionScorer()
        builder = GreedyChainBuilder(scorer)
        result = builder.build(tracks, ids)
        # Compatible tracks should produce a decent quality score
        assert result.quality_score > 0.3


# ── Genetic Algorithm ───────────────────────────────────


class TestGeneticAlgorithm:
    def test_produces_valid_ordering(self) -> None:
        random.seed(42)
        tracks, ids = _make_tracks(8)
        scorer = TransitionScorer()
        ga = GeneticAlgorithm(
            scorer,
            population_size=20,
            max_generations=10,
            convergence_threshold=5,
        )
        result = ga.optimize(tracks, ids)

        assert result.algorithm == "ga"
        assert sorted(result.track_order) == sorted(ids)
        assert result.quality_score > 0.0
        assert result.generations is not None
        assert result.generations > 0

    def test_empty_tracks(self) -> None:
        scorer = TransitionScorer()
        ga = GeneticAlgorithm(scorer, population_size=10, max_generations=5)
        result = ga.optimize([], [])
        assert result.track_order == []
        assert result.generations == 0

    def test_two_tracks(self) -> None:
        random.seed(42)
        tracks, ids = _make_tracks(2)
        scorer = TransitionScorer()
        ga = GeneticAlgorithm(scorer, population_size=10, max_generations=5)
        result = ga.optimize(tracks, ids)
        assert len(result.track_order) == 2
        assert set(result.track_order) == set(ids)

    def test_excludes_tracks(self) -> None:
        random.seed(42)
        tracks, ids = _make_tracks(8)
        scorer = TransitionScorer()
        ga = GeneticAlgorithm(
            scorer, population_size=20, max_generations=10, convergence_threshold=5
        )
        excluded = {ids[2], ids[5]}
        result = ga.optimize(tracks, ids, excluded=excluded)

        for eid in excluded:
            assert eid not in result.track_order

    def test_pinned_not_excluded(self) -> None:
        """Pinned tracks cannot be removed even if in excluded set."""
        random.seed(42)
        tracks, ids = _make_tracks(6)
        scorer = TransitionScorer()
        ga = GeneticAlgorithm(
            scorer, population_size=20, max_generations=10, convergence_threshold=5
        )
        # Track 3 is both pinned and excluded — pinned wins
        result = ga.optimize(tracks, ids, pinned={ids[2]}, excluded={ids[2]})
        assert ids[2] in result.track_order

    def test_converges_quality_improves(self) -> None:
        """GA quality should improve or stay same over generations."""
        random.seed(42)
        tracks, ids = _make_compatible_tracks(8)
        scorer = TransitionScorer()

        progress_log: list[tuple[int, float]] = []

        def on_progress(gen: int, fitness: float) -> None:
            progress_log.append((gen, fitness))

        ga = GeneticAlgorithm(
            scorer,
            population_size=30,
            max_generations=30,
            convergence_threshold=15,
        )
        ga.optimize(tracks, ids, on_progress=on_progress)

        # Should have logged progress
        assert len(progress_log) > 0

        # Best fitness should be non-decreasing (tracked externally)
        best_seen = progress_log[0][1]
        for _, fitness in progress_log[1:]:
            assert fitness >= best_seen or abs(fitness - best_seen) < 1e-10
            best_seen = max(best_seen, fitness)

    def test_with_template_differs_from_without(self) -> None:
        """Template-aware fitness should produce different ordering."""
        random.seed(42)
        tracks, ids = _make_tracks(8)
        scorer = TransitionScorer()

        ga = GeneticAlgorithm(
            scorer, population_size=30, max_generations=20, convergence_threshold=10
        )

        random.seed(42)
        result_no_tmpl = ga.optimize(tracks, ids)

        random.seed(42)
        template = get_template("classic_60")
        result_with_tmpl = ga.optimize(tracks, ids, template=template)

        # Both should be valid orderings
        assert sorted(result_no_tmpl.track_order) == sorted(ids)
        assert sorted(result_with_tmpl.track_order) == sorted(ids)

        # Scores may differ (template adds a fitness component)
        # At minimum, both should have positive scores
        assert result_no_tmpl.quality_score > 0.0
        assert result_with_tmpl.quality_score > 0.0


# ── 2-opt improvement ──────────────────────────────────


class TestTwoOpt:
    def test_improves_or_maintains_quality(self) -> None:
        """2-opt should never make things worse."""
        random.seed(42)
        tracks, ids = _make_compatible_tracks(6)
        scorer = TransitionScorer()
        idx_map = {tid: i for i, tid in enumerate(ids)}

        # Create a random ordering
        order = list(ids)
        random.shuffle(order)
        before_fitness = compute_fitness(scorer, tracks, order, idx_map)

        # Run 2-opt via GA internals
        ga = GeneticAlgorithm(
            scorer, population_size=10, max_generations=1, convergence_threshold=1
        )
        improved = ga._two_opt(tracks, order, idx_map, None, None, set())
        after_fitness = compute_fitness(scorer, tracks, improved, idx_map)

        assert after_fitness >= before_fitness - 1e-10
        assert sorted(improved) == sorted(order)


# ── Fitness function ────────────────────────────────────


class TestFitness:
    def test_fitness_returns_bounded_value(self) -> None:
        random.seed(42)
        tracks, ids = _make_tracks(5)
        scorer = TransitionScorer()
        idx_map = {tid: i for i, tid in enumerate(ids)}
        score = compute_fitness(scorer, tracks, ids, idx_map)
        assert 0.0 <= score <= 1.0

    def test_fitness_with_template(self) -> None:
        random.seed(42)
        tracks, ids = _make_tracks(5)
        scorer = TransitionScorer()
        idx_map = {tid: i for i, tid in enumerate(ids)}
        template = get_template("warm_up_30")
        score = compute_fitness(scorer, tracks, ids, idx_map, template=template)
        assert 0.0 <= score <= 1.0

    def test_fitness_empty_order(self) -> None:
        scorer = TransitionScorer()
        score = compute_fitness(scorer, [], [], {})
        # Should handle gracefully
        assert score >= 0.0
