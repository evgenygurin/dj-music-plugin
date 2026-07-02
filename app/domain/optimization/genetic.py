"""Genetic algorithm optimizer for DJ set track ordering."""

from __future__ import annotations

import random
from collections.abc import Callable

from app.config import get_settings
from app.domain.optimization.fitness import compute_fitness
from app.domain.optimization.result import OptimizationResult
from app.domain.template.models import SetTemplateDefinition
from app.domain.transition.bulk_scorer import extract_feature_arrays, score_pairs_bulk
from app.domain.transition.hard_constraints import check_hard_constraints
from app.domain.transition.intent import TransitionIntent
from app.domain.transition.pair_context import build_pair_context
from app.domain.transition.scorer import TransitionScorer
from app.domain.transition.section_context import SectionContext
from app.shared.features import TrackFeatures

# Pool prefilter: drop tracks with fewer than this many viable
# outbound + inbound transitions (under hard constraints). Such
# tracks are isolated points the GA can't usefully sequence — keeping
# them just costs scoring time and rarely helps the fitness gradient.
_MIN_VIABLE_DEGREE = 5

# Maximum reverse-segment span considered by 2-opt. Long reverses
# (j - i much larger than ~12) flatten the energy arc and rarely beat
# the GA-supplied ordering at peak time — they trade local groove for
# global structure. Bounding the window keeps 2-opt at O(N·W) per pass
# instead of O(N²), which dominates wall-clock for pools >100 tracks.
_TWO_OPT_WINDOW = 12

# Intents the scorer can be called with under ``infer_intent``. Used by
# the eager pre-compute pass so the GA + 2-opt loop never has to enter
# ``scorer.score`` again — every fitness call lands on a dict-lookup.
_PRECOMPUTE_INTENTS: tuple[TransitionIntent, ...] = (
    TransitionIntent.MAINTAIN,
    TransitionIntent.RAMP_UP,
    TransitionIntent.COOL_DOWN,
    TransitionIntent.CONTRAST,
)


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
        settings = get_settings().optimization
        self.scorer = scorer
        self.population_size = population_size or settings.population_size
        self.max_generations = max_generations or settings.max_generations
        self.mutation_rate = mutation_rate or settings.mutation_rate
        self.elitism_rate = elitism_rate or settings.elitism_rate
        self.tournament_size = tournament_size or settings.tournament_size
        self.convergence_threshold = convergence_threshold or settings.convergence_threshold

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

        # ── Stage 1: cheap O(N²) pairwise hard-reject precompute ──
        # ``check_hard_constraints`` is plain arithmetic (BPM diff,
        # Camelot distance, LUFS gap). For a 200-track pool it's
        # ~40 k cheap calls (<200 ms) but lets the GA loop skip the
        # heavy stem-aware ``scorer.score`` for those pairs entirely.
        reject_mask = self._precompute_reject_mask(tracks, active_ids, idx_map)

        # ── Stage 2: pool prefilter — drop low-connectivity tracks ──
        # Tracks with very few viable neighbours are isolated points
        # the GA can't usefully sequence: they show up at the start /
        # end with no good options no matter what. Pinned ids are
        # immune to the filter.
        active_ids = self._prefilter_pool(active_ids, idx_map, reject_mask, pinned)
        n = len(active_ids)
        if n == 0:
            return OptimizationResult(
                track_order=[], quality_score=0.0, generations=0, algorithm="ga"
            )
        if n <= 2:
            quality = compute_fitness(
                self.scorer,
                tracks,
                active_ids,
                idx_map,
                template,
                moods,
                reject_mask=reject_mask,
            )
            return OptimizationResult(
                track_order=list(active_ids),
                quality_score=quality,
                generations=0,
                algorithm="ga",
            )

        # ── Stage 3: eager-populated score cache for the GA loop ──
        # ``transition_quality`` keys its memo by ``(idx_a, idx_b,
        # intent.value)``. ``infer_intent`` only ever returns one of
        # the enum values in ``_PRECOMPUTE_INTENTS``, so the surviving
        # pair set is finite and we can fill the cache exhaustively
        # *before* the GA starts. After this pass, every fitness call
        # the GA + 2-opt make lands on a dict lookup — ``scorer.score``
        # is never re-entered, even for the very first generation.
        # Cost: ``|surviving_pairs| · |intents|`` scorer calls (under
        # ~10 k for typical 200-track pools after prefilter), measured
        # in single-digit seconds. Saving: removes the 5-10 generation
        # warm-up tax the GA used to pay before its cache stabilised,
        # and lets the inner loops stay pure Python lookups.
        score_cache: dict[tuple[int, int, str, str | None], float] = {}
        self._eager_populate_cache(tracks, active_ids, idx_map, reject_mask, score_cache)

        population = self._init_population(active_ids, pinned)
        best_individual = population[0]
        best_fitness = self._fitness(
            tracks, best_individual, idx_map, template, moods, score_cache, reject_mask
        )
        stagnant = 0
        gen = 0

        for gen in range(self.max_generations):
            fitness_scores = [
                self._fitness(tracks, ind, idx_map, template, moods, score_cache, reject_mask)
                for ind in population
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
                on_progress(
                    int(((gen + 1) / max(1, self.max_generations)) * 100),
                    best_fitness,
                )

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

        best_individual = self._two_opt(
            tracks, best_individual, idx_map, template, moods, pinned, score_cache, reject_mask
        )
        best_fitness = self._fitness(
            tracks, best_individual, idx_map, template, moods, score_cache, reject_mask
        )
        if on_progress is not None:
            on_progress(100, best_fitness)

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
        score_cache: dict[tuple[int, int, str, str | None], float] | None = None,
        reject_mask: set[tuple[int, int]] | None = None,
    ) -> float:
        return compute_fitness(
            self.scorer,
            tracks,
            order,
            idx_map,
            template,
            moods,
            score_cache=score_cache,
            reject_mask=reject_mask,
        )

    # ── Pre-pass helpers ────────────────────────────────

    @staticmethod
    def _precompute_reject_mask(
        tracks: list[TrackFeatures],
        active_ids: list[int],
        idx_map: dict[int, int],
    ) -> set[tuple[int, int]]:
        """Return the set of ``(idx_a, idx_b)`` pairs that fail hard constraints.

        Cheap O(N²) pre-pass — each call to ``check_hard_constraints`` is
        a handful of comparisons (BPM diff, Camelot distance, LUFS gap).
        For typical techno pools the rejection rate is 70-95 %, so this
        upfront cost converts into a 5-20x wall-clock saving over the
        full GA + 2-opt run.
        """
        reject: set[tuple[int, int]] = set()
        indices = [idx_map[tid] for tid in active_ids]
        for i, idx_a in enumerate(indices):
            a = tracks[idx_a]
            for idx_b in indices[i + 1 :]:
                b = tracks[idx_b]
                if check_hard_constraints(a, b) is not None:
                    reject.add((idx_a, idx_b))
                # Hard constraints are symmetric (BPM diff and energy
                # gap are absolute, Camelot distance is symmetric) so
                # one call covers both directions.
                if check_hard_constraints(b, a) is not None:
                    reject.add((idx_b, idx_a))
        return reject

    @staticmethod
    def _prefilter_pool(
        active_ids: list[int],
        idx_map: dict[int, int],
        reject_mask: set[tuple[int, int]],
        pinned: set[int],
        min_degree: int = _MIN_VIABLE_DEGREE,
    ) -> list[int]:
        """Drop tracks with fewer than ``min_degree`` viable neighbours.

        A track that hard-rejects against most of the pool is an
        isolated node — including it just costs scoring time and rarely
        improves fitness. Pinned ids are kept regardless.
        """
        if not reject_mask:
            return active_ids

        kept: list[int] = []
        for tid in active_ids:
            if tid in pinned:
                kept.append(tid)
                continue
            idx = idx_map[tid]
            viable_out = sum(
                1
                for other in active_ids
                if other != tid and (idx, idx_map[other]) not in reject_mask
            )
            viable_in = sum(
                1
                for other in active_ids
                if other != tid and (idx_map[other], idx) not in reject_mask
            )
            if viable_out >= min_degree and viable_in >= min_degree:
                kept.append(tid)
        # Never strip the pool below 2 tracks — the GA needs at least
        # a pair to do anything meaningful.
        if len(kept) < 2:
            return active_ids
        return kept

    def _eager_populate_cache(
        self,
        tracks: list[TrackFeatures],
        active_ids: list[int],
        idx_map: dict[int, int],
        reject_mask: set[tuple[int, int]],
        score_cache: dict[tuple[int, int, str, str | None], float],
    ) -> None:
        """Pre-fill ``score_cache`` for every surviving (a, b, intent) triple.

        After this returns, ``compute_fitness`` lands on a dict-lookup
        for every consecutive pair regardless of which order the GA is
        evaluating — there is no cold-start tax on the first generation
        and 2-opt's O(N·W) reverse-trial scan never re-enters the
        scorer either. Pairs in ``reject_mask`` are skipped (fitness
        contributes ``0.0`` for them via the mask, no cache entry needed).

        Implementation goes through ``bulk_scorer.score_pairs_bulk`` —
        every component (BPM, energy, four stem compats) is a numpy
        bulk op over the surviving (idx_a, idx_b) pair arrays. The
        intent loop fans the same precomputed stem matrix into four
        weighted sums via broadcasting. The bulk path is ``np.allclose``-
        equivalent to the scalar path used by ``transition_score_pool``
        and ``ui_transition_score`` (parity-tested in
        ``tests/domain/transition/test_bulk_scorer_parity.py``).

        On a real ``Subgenre: peak_time`` 242-track pool this stage
        drops from ~3-4 s (intent-share serial) / ~3 s (parallel) to
        sub-second, and tests/benchmark show ~5-10x compared to the
        scalar Python loop on dense (low-reject-rate) workloads.
        """
        indices = [idx_map[tid] for tid in active_ids]
        generic_pairs: list[tuple[int, int]] = []
        contextual_pairs: list[tuple[int, int, SectionContext]] = []
        for idx_a in indices:
            for idx_b in indices:
                if idx_a == idx_b:
                    continue
                if (idx_a, idx_b) in reject_mask:
                    continue
                context = build_pair_context(
                    tracks[idx_a],
                    tracks[idx_b],
                    position=0.5,
                ).section_context
                if context is None:
                    generic_pairs.append((idx_a, idx_b))
                else:
                    contextual_pairs.append((idx_a, idx_b, context))

        if generic_pairs:
            fa = extract_feature_arrays(tracks)
            bulk = score_pairs_bulk(fa, generic_pairs, _PRECOMPUTE_INTENTS)
            score_cache.update(
                {
                    (idx_a, idx_b, intent, None): value
                    for (idx_a, idx_b, intent), value in bulk.items()
                }
            )

        for idx_a, idx_b, section_context in contextual_pairs:
            scores = self.scorer.score_all_intents(
                tracks[idx_a],
                tracks[idx_b],
                _PRECOMPUTE_INTENTS,
                section_context=section_context,
            )
            pair_class = section_context.section_pair_class.value
            for intent, score in scores.items():
                score_cache[(idx_a, idx_b, intent.value, pair_class)] = (
                    0.0 if score.hard_reject else score.overall
                )

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
        score_cache: dict[tuple[int, int, str, str | None], float] | None = None,
        reject_mask: set[tuple[int, int]] | None = None,
    ) -> list[int]:
        """2-opt improvement with adaptive window expansion.

        Strategy:

        * Start with ``window = _TWO_OPT_WINDOW`` (12) — most useful
          improvements are local groove repairs within ~12 positions.
        * On a pass that finds an improvement, restart at the same
          window — short reverses are cheap and frequently chain.
        * On a pass that finds nothing at the current window, **double
          the window** and try again. This catches the long reverses
          that fix global energy-arc issues without paying O(N²) on
          every pass — only when the local search has plateaued.
        * Bail out when a pass at ``window = n - 1`` (full O(N²))
          still finds nothing, or when ``max_passes`` is exhausted.

        Bounds:

        * ``max_passes = settings.optimization.two_opt_iterations``
          caps the total number of passes regardless of window. Wide
          passes still cost more, but the cap prevents runaway loops.
        * Each pass keeps first-improvement semantics: it restarts as
          soon as any reverse beats current best fitness.
        """
        n = len(order)
        if n <= 3:
            return order

        max_passes = get_settings().optimization.two_opt_iterations
        full_window = n - 1
        window = min(full_window, _TWO_OPT_WINDOW)

        best = list(order)
        best_fitness = self._fitness(
            tracks, best, idx_map, template, moods, score_cache, reject_mask
        )

        passes_used = 0
        while passes_used < max_passes:
            improved = False
            for i in range(n - 1):
                j_max = min(full_window, i + window)
                for j in range(i + 2, j_max + 1):
                    candidate = list(best)
                    candidate[i : j + 1] = reversed(candidate[i : j + 1])
                    f = self._fitness(
                        tracks, candidate, idx_map, template, moods, score_cache, reject_mask
                    )
                    if f > best_fitness:
                        best = candidate
                        best_fitness = f
                        improved = True
                        break
                if improved:
                    break
            passes_used += 1

            if improved:
                # Found a hit at this window — keep the cheap path open
                # for the next pass instead of widening prematurely.
                continue
            if window >= full_window:
                # No improvement even at the full O(N²) sweep — this
                # ordering is locally optimal under 2-opt.
                break
            # Plateau at the current window: try wider next pass.
            window = min(full_window, window * 2)

        return best
