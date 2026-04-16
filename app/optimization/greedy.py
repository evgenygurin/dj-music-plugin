"""Greedy chain builder — fast O(n^2) heuristic for set optimization."""

from __future__ import annotations

from collections.abc import Callable

from app.entities.audio.features import TrackFeatures
from app.optimization.candidate_filter import build_adjacency
from app.optimization.fitness import compute_fitness
from app.optimization.result import OptimizationResult
from app.templates.models import SetTemplateDefinition
from app.transition.scorer import TransitionScorer


class GreedyChainBuilder:
    """Fast O(n^2): greedily pick best next transition at each step."""

    def __init__(self, scorer: TransitionScorer) -> None:
        self.scorer = scorer

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
        """Build chain starting from best opening track.

        Conforms to OptimizerStrategy protocol.
        Pinned tracks must all appear in the result (cannot be removed).
        """
        excluded = excluded or set()
        pinned = pinned or set()
        active_ids = [tid for tid in track_ids if tid not in excluded or tid in pinned]

        if len(active_ids) == 0:
            return OptimizationResult(track_order=[], quality_score=0.0)

        idx_map = {tid: i for i, tid in enumerate(track_ids)}
        # Pre-compute adjacency graph (hard-constraint pre-filter)
        features_map = {tid: tracks[idx_map[tid]] for tid in active_ids}
        adjacency = build_adjacency(features_map)
        remaining = set(active_ids)

        def _opener_score(tid: int) -> float:
            feat = tracks[idx_map[tid]]
            lufs = feat.integrated_lufs if feat.integrated_lufs is not None else -10.0
            bpm = feat.bpm if feat.bpm is not None else 130.0
            return lufs + (bpm - 120.0) * 0.1

        order: list[int] = []
        current = min(remaining, key=_opener_score)
        order.append(current)
        remaining.remove(current)

        while remaining:
            # Use pre-filtered candidates; fall back to all remaining if graph gives nothing
            candidates = adjacency.get(current, set()) & remaining
            if not candidates:
                candidates = remaining  # fallback: no valid transitions, take any

            best_tid = None
            best_score = -1.0
            for candidate in candidates:
                result = self.scorer.score(
                    tracks[idx_map[current]],
                    tracks[idx_map[candidate]],
                )
                score = 0.0 if result.hard_reject else result.overall
                if score > best_score:
                    best_score = score
                    best_tid = candidate
            if best_tid is None:
                best_tid = next(iter(remaining))
            order.append(best_tid)
            remaining.remove(best_tid)
            current = best_tid

        quality = compute_fitness(self.scorer, tracks, order, idx_map, template, moods)
        return OptimizationResult(
            track_order=order,
            quality_score=quality,
            algorithm="greedy",
        )

    def build(
        self,
        tracks: list[TrackFeatures],
        track_ids: list[int],
        pinned: set[int] | None = None,
    ) -> OptimizationResult:
        """Backward-compatible alias for optimize()."""
        return self.optimize(tracks, track_ids, pinned=pinned)
