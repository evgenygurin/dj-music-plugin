"""Set generation — GA optimizer and greedy chain builder.

Two algorithms for finding optimal track ordering in a DJ set:
- GreedyChainBuilder: O(n^2) fast heuristic
- GeneticAlgorithm: population-based optimization with 2-opt post-processing
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass

from app.config import settings
from app.core.transition_intent import infer_intent
from app.services.templates import SetTemplateDefinition
from app.services.transition import TrackFeatures, TransitionScorer


@dataclass
class OptimizationResult:
    """Result of set optimization — ordered track IDs with quality metrics."""

    track_order: list[int]
    quality_score: float
    generations: int | None = None
    algorithm: str = "greedy"


# ── Fitness helpers ─────────────────────────────────────


def _transition_quality(
    scorer: TransitionScorer,
    tracks: list[TrackFeatures],
    order: list[int],
    idx_map: dict[int, int],
) -> float:
    """Average transition score across consecutive pairs, using intent-aware weights."""
    if len(order) < 2:
        return 1.0
    total = 0.0
    n = len(order)
    for i in range(n - 1):
        a = tracks[idx_map[order[i]]]
        b = tracks[idx_map[order[i + 1]]]
        position = i / max(1, n - 2)  # 0.0 to 1.0
        energy_delta = (b.integrated_lufs or -8.0) - (a.integrated_lufs or -8.0)
        intent = infer_intent(position, energy_delta)
        score = scorer.score(a, b, intent=intent)
        total += 0.0 if score.hard_reject else score.overall
    return total / (n - 1)


def _bpm_smoothness(
    tracks: list[TrackFeatures],
    order: list[int],
    idx_map: dict[int, int],
) -> float:
    """Penalize large BPM jumps between consecutive tracks. Returns 0-1."""
    if len(order) < 2:
        return 1.0
    total = 0.0
    count = 0
    for i in range(len(order) - 1):
        a = tracks[idx_map[order[i]]]
        b = tracks[idx_map[order[i + 1]]]
        if a.bpm is not None and b.bpm is not None:
            diff = abs(a.bpm - b.bpm)
            # Gaussian: sigma=4 BPM
            total += math.exp(-(diff**2) / 32.0)
            count += 1
    return total / count if count > 0 else 0.5


def _energy_arc_score(
    tracks: list[TrackFeatures],
    order: list[int],
    idx_map: dict[int, int],
) -> float:
    """Reward a natural energy arc (build up then ease off). Returns 0-1."""
    if len(order) < 3:
        return 0.5
    n = len(order)
    total = 0.0
    for i, tid in enumerate(order):
        t = tracks[idx_map[tid]]
        if t.integrated_lufs is None:
            continue
        # Ideal arc: energy peaks around 65-75% of the set
        pos = i / (n - 1)
        # Target LUFS: parabolic arc peaking at position 0.7
        ideal_peak_pos = 0.7
        arc = -(4.0 * (pos - ideal_peak_pos) ** 2) + 1.0
        # Map arc [0,1] to LUFS range [-14, -6]
        ideal_lufs = -14.0 + arc * 8.0
        # Score: how close actual LUFS is to ideal
        diff = abs(t.integrated_lufs - ideal_lufs)
        total += math.exp(-(diff**2) / 18.0)  # sigma ~3 LUFS
    return total / n


def _subgenre_variety(
    tracks: list[TrackFeatures],
    order: list[int],
    idx_map: dict[int, int],
    moods: dict[int, str | None] | None = None,
) -> float:
    """Reward variety of moods/subgenres in the set. Returns 0-1."""
    if moods is None or len(order) < 2:
        return 0.5
    unique = set()
    for tid in order:
        mood = moods.get(tid)
        if mood is not None:
            unique.add(mood)
    # Normalize: having 4+ distinct moods is ideal
    return min(1.0, len(unique) / 4.0)


def _template_fitness(
    tracks: list[TrackFeatures],
    order: list[int],
    idx_map: dict[int, int],
    template: SetTemplateDefinition,
    moods: dict[int, str | None] | None = None,
) -> float:
    """Score how well the ordering fits the template slots. Returns 0-1."""
    if not template.slots or len(order) == 0:
        return 0.5
    n = len(order)
    total = 0.0
    slot_count = 0

    for slot in template.slots:
        # Find the track closest to this slot position
        track_idx = min(n - 1, max(0, int(slot.position * n)))
        tid = order[track_idx]
        t = tracks[idx_map[tid]]

        score = 0.0
        components = 0

        # BPM fit
        if t.bpm is not None:
            if slot.bpm_min <= t.bpm <= slot.bpm_max:
                score += 1.0
            else:
                dist = min(abs(t.bpm - slot.bpm_min), abs(t.bpm - slot.bpm_max))
                score += max(0.0, 1.0 - dist / 10.0)
            components += 1

        # Energy fit (LUFS)
        if t.integrated_lufs is not None:
            lufs_diff = abs(t.integrated_lufs - slot.energy_lufs)
            score += math.exp(-(lufs_diff**2) / 8.0)
            components += 1

        # Mood fit
        if moods and slot.target_mood is not None:
            track_mood = moods.get(tid)
            if track_mood == slot.target_mood:
                score += 1.0
            elif track_mood is not None:
                score += 0.3  # partial credit for having a mood
            components += 1

        if components > 0:
            # Flexibility reduces the penalty for poor fit
            slot_score = score / components
            slot_score = slot_score * (1.0 - slot.flexibility) + slot.flexibility
            total += slot_score
        slot_count += 1

    return total / slot_count if slot_count > 0 else 0.5


# ── Fitness weights ─────────────────────────────────────

_FITNESS_WEIGHTS = {
    "transition": 0.35,
    "bpm_smooth": 0.20,
    "energy_arc": 0.20,
    "variety": 0.10,
    "template": 0.15,
}


def compute_fitness(
    scorer: TransitionScorer,
    tracks: list[TrackFeatures],
    order: list[int],
    idx_map: dict[int, int],
    template: SetTemplateDefinition | None = None,
    moods: dict[int, str | None] | None = None,
) -> float:
    """Weighted fitness for a track ordering. Returns 0-1."""
    w = _FITNESS_WEIGHTS

    trans = _transition_quality(scorer, tracks, order, idx_map)
    bpm = _bpm_smoothness(tracks, order, idx_map)
    energy = _energy_arc_score(tracks, order, idx_map)
    variety = _subgenre_variety(tracks, order, idx_map, moods)

    if template is not None:
        tmpl = _template_fitness(tracks, order, idx_map, template, moods)
        score = (
            w["transition"] * trans
            + w["bpm_smooth"] * bpm
            + w["energy_arc"] * energy
            + w["variety"] * variety
            + w["template"] * tmpl
        )
    else:
        # Redistribute template weight proportionally
        base = 1.0 - w["template"]
        score = (
            (w["transition"] / base) * trans
            + (w["bpm_smooth"] / base) * bpm
            + (w["energy_arc"] / base) * energy
            + (w["variety"] / base) * variety
        )

    return score


# ── Greedy Chain Builder ────────────────────────────────


class GreedyChainBuilder:
    """Fast O(n^2): greedily pick best next transition at each step."""

    def __init__(self, scorer: TransitionScorer) -> None:
        self.scorer = scorer

    def build(
        self,
        tracks: list[TrackFeatures],
        track_ids: list[int],
        pinned: set[int] | None = None,
    ) -> OptimizationResult:
        """Build chain starting from best opening track.

        Pinned tracks must all appear in the result (cannot be removed).
        """
        if len(tracks) == 0:
            return OptimizationResult(track_order=[], quality_score=0.0)

        pinned = pinned or set()
        idx_map = {tid: i for i, tid in enumerate(track_ids)}
        remaining = set(track_ids)

        # Start with the track that has lowest energy (best opener)
        def _opener_score(tid: int) -> float:
            t = tracks[idx_map[tid]]
            lufs = t.integrated_lufs if t.integrated_lufs is not None else -10.0
            bpm = t.bpm if t.bpm is not None else 130.0
            # Prefer low energy + low BPM for openers
            return lufs + (bpm - 120.0) * 0.1

        order: list[int] = []
        current = min(remaining, key=_opener_score)
        order.append(current)
        remaining.remove(current)

        while remaining:
            best_tid = None
            best_score = -1.0
            for candidate in remaining:
                result = self.scorer.score(
                    tracks[idx_map[current]],
                    tracks[idx_map[candidate]],
                )
                s = 0.0 if result.hard_reject else result.overall
                if s > best_score:
                    best_score = s
                    best_tid = candidate
            if best_tid is None:
                # All remaining are hard-rejected — pick first remaining
                best_tid = next(iter(remaining))
            order.append(best_tid)
            remaining.remove(best_tid)
            current = best_tid

        quality = compute_fitness(self.scorer, tracks, order, idx_map)
        return OptimizationResult(
            track_order=order,
            quality_score=quality,
            algorithm="greedy",
        )


# ── Genetic Algorithm ───────────────────────────────────


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

        # Filter out excluded tracks but keep pinned
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

        # Initialize population with random permutations
        population = self._init_population(active_ids, pinned)
        best_individual = population[0]
        best_fitness = self._fitness(tracks, best_individual, idx_map, template, moods)
        stagnant = 0
        gen = 0

        for gen in range(self.max_generations):
            # Evaluate fitness
            fitness_scores = [
                self._fitness(tracks, ind, idx_map, template, moods) for ind in population
            ]

            # Track best
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

            # Convergence check
            if stagnant >= self.convergence_threshold:
                break

            # Elitism: keep top N%
            elite_count = max(1, int(self.population_size * self.elitism_rate))
            ranked = sorted(
                range(len(population)),
                key=lambda i: fitness_scores[i],
                reverse=True,
            )
            new_population: list[list[int]] = [
                list(population[ranked[i]]) for i in range(elite_count)
            ]

            # Fill rest with offspring
            while len(new_population) < self.population_size:
                parent_a = self._tournament_select(population, fitness_scores)
                parent_b = self._tournament_select(population, fitness_scores)
                child = self._ox_crossover(parent_a, parent_b)
                child = self._mutate(child, pinned)
                new_population.append(child)

            population = new_population

        # 2-opt local search on best
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

        # Select random segment from parent_a
        start = random.randint(0, n - 2)
        end = random.randint(start + 1, n - 1)

        child = [-1] * n
        # Copy segment from parent_a
        segment = set(parent_a[start : end + 1])
        for i in range(start, end + 1):
            child[i] = parent_a[i]

        # Fill remaining positions from parent_b in order
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
