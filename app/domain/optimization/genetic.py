"""Genetic algorithm optimizer for DJ set track ordering."""

from __future__ import annotations

import random
from collections.abc import Callable

from app.config import settings
from app.core.track_features import TrackFeatures
from app.domain.optimization.fitness import compute_fitness
from app.domain.optimization.result import OptimizationResult
from app.domain.templates.models import SetTemplateDefinition
from app.domain.transition.scorer import TransitionScorer


class GeneticAlgorithm:
    """GA optimizer for set track ordering with 2-opt post-processing."""

    def __init__(
        self,
        scorer: TransitionScorer,
        population_size: int | None = None,
        max_generations: int | None = None,
        mutation_rate: float | None = None,
        elitism_rate: float | None = None,
        tournament_size: int | None = None,
        convergence_threshold: int | None = None,
    ) -> None:
        self.scorer = scorer
        self.population_size = population_size or settings.ga_population_size
        self.max_generations = max_generations or settings.ga_max_generations
        self.mutation_rate = mutation_rate or settings.ga_mutation_rate
        self.elitism_rate = elitism_rate or settings.ga_elitism_rate
        self.tournament_size = tournament_size or settings.ga_tournament_size
        self.convergence_threshold = convergence_threshold or settings.ga_convergence_threshold

    def optimize(
        self,
        tracks: list[TrackFeatures],
        track_ids: list[int],
        pinned: set[int] | None = None,
        excluded: set[int] | None = None,
        template: SetTemplateDefinition | None = None,
        moods: dict[int, str | None] | None = None,
        on_progress: Callable[[int, float], None] | None = None,
    ) -> OptimizationResult:
        """Run GA optimization.

        Conforms to OptimizerStrategy protocol.

        Args:
            tracks: Feature data for each track (parallel with track_ids).
            track_ids: Track IDs corresponding to tracks list.
            pinned: Track IDs that must remain in the set.
            excluded: Track IDs banned from the set.
            template: Optional template for template-aware fitness.
            moods: Mapping of track_id -> mood string for variety scoring.
            on_progress: Callback(generation, best_fitness) for progress.

        Returns:
            OptimizationResult with best ordering found.
        """
        pinned = pinned or set()
        excluded = excluded or set()

        active_ids = [tid for tid in track_ids if tid not in excluded or tid in pinned]
        idx_map = {tid: i for i, tid in enumerate(track_ids)}

        n = len(active_ids)
        if n == 0:
            return OptimizationResult(
                track_order=[], quality_score=0.0, generations=0, algorithm="ga"
            )
        if n <= 2:
            quality = compute_fitness(self.scorer, tracks, active_ids, idx_map, template, moods)
            return OptimizationResult(
                track_order=list(active_ids),
                quality_score=quality,
                generations=0,
                algorithm="ga",
            )

        population = self._init_population(active_ids, pinned)
        best_individual = population[0]
        best_fitness = self._fitness(tracks, best_individual, idx_map, template, moods)
        stagnant = 0
        gen = 0

        for gen in range(self.max_generations):
            fitness_scores = [
                self._fitness(tracks, ind, idx_map, template, moods) for ind in population
            ]

            gen_best_idx = max(range(len(fitness_scores)), key=lambda i: fitness_scores[i])
            gen_best_fitness = fitness_scores[gen_best_idx]

            if gen_best_fitness > best_fitness:
                best_fitness = gen_best_fitness
                best_individual = list(population[gen_best_idx])
                stagnant = 0
            else:
                stagnant += 1

            if on_progress is not None:
                on_progress(gen, best_fitness)

            if stagnant >= self.convergence_threshold:
                break

            elite_count = max(1, int(self.population_size * self.elitism_rate))
            ranked = sorted(
                range(len(population)),
                key=lambda i: fitness_scores[i],
                reverse=True,
            )
            new_population: list[list[int]] = [
                list(population[ranked[i]]) for i in range(elite_count)
            ]

            while len(new_population) < self.population_size:
                parent_a = self._tournament_select(population, fitness_scores)
                parent_b = self._tournament_select(population, fitness_scores)
                child = self._ox_crossover(parent_a, parent_b)
                child = self._mutate(child, pinned)
                new_population.append(child)

            population = new_population

        best_individual = self._two_opt(tracks, best_individual, idx_map, template, moods, pinned)
        best_fitness = self._fitness(tracks, best_individual, idx_map, template, moods)

        return OptimizationResult(
            track_order=best_individual,
            quality_score=best_fitness,
            generations=gen + 1,
            algorithm="ga",
        )

    # ── Population initialization ───────────────────────

    def _init_population(self, track_ids: list[int], pinned: set[int]) -> list[list[int]]:
        """Create initial population of random permutations."""
        population: list[list[int]] = []
        for _ in range(self.population_size):
            individual = list(track_ids)
            random.shuffle(individual)
            population.append(individual)
        return population

    # ── Fitness evaluation ──────────────────────────────

    def _fitness(
        self,
        tracks: list[TrackFeatures],
        order: list[int],
        idx_map: dict[int, int],
        template: SetTemplateDefinition | None,
        moods: dict[int, str | None] | None,
    ) -> float:
        return compute_fitness(self.scorer, tracks, order, idx_map, template, moods)

    # ── Selection ───────────────────────────────────────

    def _tournament_select(
        self,
        population: list[list[int]],
        fitness_scores: list[float],
    ) -> list[int]:
        """Tournament selection: pick best from random subset."""
        indices = random.sample(
            range(len(population)),
            min(self.tournament_size, len(population)),
        )
        best = max(indices, key=lambda i: fitness_scores[i])
        return population[best]

    # ── Crossover (Order Crossover — OX) ────────────────

    @staticmethod
    def _ox_crossover(parent_a: list[int], parent_b: list[int]) -> list[int]:
        """Order Crossover for permutation-based chromosomes."""
        n = len(parent_a)
        if n <= 2:
            return list(parent_a)

        start = random.randint(0, n - 2)
        end = random.randint(start + 1, n - 1)

        child = [-1] * n
        segment = set(parent_a[start : end + 1])
        for i in range(start, end + 1):
            child[i] = parent_a[i]

        pos = (end + 1) % n
        for gene in parent_b:
            if gene not in segment:
                child[pos] = gene
                pos = (pos + 1) % n

        return child

    # ── Mutation ────────────────────────────────────────

    def _mutate(self, individual: list[int], pinned: set[int]) -> list[int]:
        """Apply swap, insert, or reverse mutation."""
        if random.random() > self.mutation_rate:
            return individual

        n = len(individual)
        if n <= 2:
            return individual

        mutation_type = random.choice(["swap", "insert", "reverse"])

        if mutation_type == "swap":
            i, j = random.sample(range(n), 2)
            individual[i], individual[j] = individual[j], individual[i]
        elif mutation_type == "insert":
            i = random.randint(0, n - 1)
            j = random.randint(0, n - 1)
            gene = individual.pop(i)
            individual.insert(j, gene)
        else:  # reverse
            i, j = sorted(random.sample(range(n), 2))
            individual[i : j + 1] = reversed(individual[i : j + 1])

        return individual

    # ── 2-opt local search ──────────────────────────────

    def _two_opt(
        self,
        tracks: list[TrackFeatures],
        order: list[int],
        idx_map: dict[int, int],
        template: SetTemplateDefinition | None,
        moods: dict[int, str | None] | None,
        pinned: set[int],
    ) -> list[int]:
        """2-opt improvement: try reversing every sub-segment."""
        n = len(order)
        if n <= 3:
            return order

        best = list(order)
        best_fitness = self._fitness(tracks, best, idx_map, template, moods)
        improved = True

        while improved:
            improved = False
            for i in range(n - 1):
                for j in range(i + 2, n):
                    candidate = list(best)
                    candidate[i : j + 1] = reversed(candidate[i : j + 1])
                    f = self._fitness(tracks, candidate, idx_map, template, moods)
                    if f > best_fitness:
                        best = candidate
                        best_fitness = f
                        improved = True
                        break
                if improved:
                    break

        return best
