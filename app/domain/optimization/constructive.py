"""Constructive slot-by-slot optimizer for template-driven set building."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from app.domain.optimization.fitness import compute_fitness
from app.domain.optimization.result import OptimizationResult
from app.domain.template.models import SetTemplateDefinition, TemplateSlot
from app.domain.transition.pair_context import build_pair_context
from app.domain.transition.scorer import TransitionScorer
from app.shared.features import TrackFeatures

_DEFAULT_BEAM_WIDTH = 6
_DEFAULT_SLOT_CANDIDATES = 18
_TRANSITION_WEIGHT = 0.60
_SLOT_WEIGHT = 0.40


@dataclass(slots=True)
class _BeamState:
    order: list[int]
    score: float
    pinned_remaining: frozenset[int]


class ConstructiveSlotBuilder:
    """Select tracks per template slot instead of reordering a fixed pool."""

    def __init__(
        self,
        scorer: TransitionScorer,
        *,
        beam_width: int = _DEFAULT_BEAM_WIDTH,
        slot_candidates: int = _DEFAULT_SLOT_CANDIDATES,
    ) -> None:
        self.scorer = scorer
        self.beam_width = beam_width
        self.slot_candidates = slot_candidates

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
        if template is None:
            raise ValueError("constructive optimizer requires a template")

        pinned = pinned or set()
        excluded = excluded or set()
        active_ids = [tid for tid in track_ids if tid not in excluded or tid in pinned]
        if not active_ids:
            return OptimizationResult(track_order=[], quality_score=0.0, algorithm="constructive")

        target_size = min(len(template.slots), len(active_ids))
        if len(pinned) > target_size:
            raise ValueError(
                "constructive optimizer cannot fit all pinned tracks into template slots"
            )

        idx_map = {tid: i for i, tid in enumerate(track_ids)}
        slot_shortlists = [
            self._slot_shortlist(
                slot=template.slots[slot_index],
                candidate_ids=active_ids,
                idx_map=idx_map,
                tracks=tracks,
                moods=moods,
                pinned=pinned,
            )
            for slot_index in range(target_size)
        ]

        states = [_BeamState(order=[], score=0.0, pinned_remaining=frozenset(pinned))]
        best_seen = 0.0

        for slot_index in range(target_size):
            slot = template.slots[slot_index]
            next_states: list[_BeamState] = []

            for state in states:
                used = set(state.order)
                slots_left = target_size - slot_index
                must_place_only_pinned = len(state.pinned_remaining) >= slots_left

                candidate_ids = (
                    sorted(state.pinned_remaining)
                    if must_place_only_pinned
                    else self._merge_candidates(
                        slot_shortlists[slot_index],
                        state.pinned_remaining,
                    )
                )

                for candidate_id in candidate_ids:
                    if candidate_id in used:
                        continue
                    pinned_remaining = state.pinned_remaining - {candidate_id}
                    if len(pinned_remaining) > target_size - len(state.order) - 1:
                        continue

                    slot_score = self._slot_score(
                        tracks[idx_map[candidate_id]],
                        slot,
                        moods.get(candidate_id) if moods is not None else None,
                    )
                    transition_score = self._transition_score(
                        order=state.order,
                        candidate_id=candidate_id,
                        idx_map=idx_map,
                        tracks=tracks,
                        template=template,
                        target_size=target_size,
                    )
                    novelty_bonus = self._novelty_bonus(
                        order=state.order,
                        candidate_id=candidate_id,
                        moods=moods,
                    )
                    next_states.append(
                        _BeamState(
                            order=[*state.order, candidate_id],
                            score=state.score
                            + _SLOT_WEIGHT * slot_score
                            + _TRANSITION_WEIGHT * transition_score
                            + novelty_bonus,
                            pinned_remaining=frozenset(pinned_remaining),
                        )
                    )

            if not next_states:
                break

            next_states.sort(
                key=lambda state: (
                    not state.pinned_remaining,
                    state.score,
                    len(state.order),
                ),
                reverse=True,
            )
            states = next_states[: self.beam_width]
            best_seen = states[0].score
            if on_progress is not None:
                on_progress(int(((slot_index + 1) / target_size) * 100), best_seen)

        best_state = max(
            states,
            key=lambda state: (
                not state.pinned_remaining,
                len(state.order),
                state.score,
            ),
        )
        quality = compute_fitness(
            self.scorer,
            tracks,
            best_state.order,
            idx_map,
            template,
            moods,
        )
        return OptimizationResult(
            track_order=best_state.order,
            quality_score=quality,
            generations=target_size,
            algorithm="constructive",
        )

    def _slot_shortlist(
        self,
        *,
        slot: TemplateSlot,
        candidate_ids: list[int],
        idx_map: dict[int, int],
        tracks: list[TrackFeatures],
        moods: dict[int, str | None] | None,
        pinned: set[int],
    ) -> list[int]:
        ranked = sorted(
            candidate_ids,
            key=lambda tid: (
                tid in pinned,
                self._slot_score(
                    tracks[idx_map[tid]],
                    slot,
                    moods.get(tid) if moods is not None else None,
                ),
            ),
            reverse=True,
        )
        return ranked[: self.slot_candidates]

    def _merge_candidates(
        self,
        shortlist: list[int],
        pinned_remaining: frozenset[int],
    ) -> list[int]:
        seen: set[int] = set()
        merged: list[int] = []
        for tid in [*sorted(pinned_remaining), *shortlist]:
            if tid in seen:
                continue
            seen.add(tid)
            merged.append(tid)
        return merged

    def _slot_score(
        self,
        features: TrackFeatures,
        slot: TemplateSlot,
        mood: str | None,
    ) -> float:
        bpm_score = 0.5
        bpm_penalty = 0.0
        if features.bpm is not None:
            center = (slot.bpm_min + slot.bpm_max) / 2
            half_range = max(1.0, (slot.bpm_max - slot.bpm_min) / 2)
            distance = abs(features.bpm - center)
            bpm_score = max(0.0, 1.0 - distance / (half_range + 3.0))
            if not slot.bpm_min <= features.bpm <= slot.bpm_max:
                edge_distance = min(
                    abs(features.bpm - slot.bpm_min),
                    abs(features.bpm - slot.bpm_max),
                )
                bpm_penalty = min(1.0, edge_distance / 8.0)

        lufs_score = 0.5
        lufs_penalty = 0.0
        if features.integrated_lufs is not None:
            diff = abs(features.integrated_lufs - slot.energy_lufs)
            lufs_score = math.exp(-((diff**2) / 10.0))
            lufs_penalty = min(1.0, diff / 8.0)

        mood_score = 0.65
        mood_penalty = 0.0
        if slot.target_mood is not None:
            if mood == slot.target_mood:
                mood_score = 1.0
            elif mood is None:
                mood_score = 0.45
                mood_penalty = 0.2
            else:
                mood_score = 0.25
                mood_penalty = 0.75

        base = 0.40 * mood_score + 0.35 * bpm_score + 0.25 * lufs_score
        strictness = 1.0 - slot.flexibility
        penalty = strictness * (0.45 * mood_penalty + 0.35 * bpm_penalty + 0.20 * lufs_penalty)
        return max(0.0, min(1.0, base - penalty))

    def _transition_score(
        self,
        *,
        order: list[int],
        candidate_id: int,
        idx_map: dict[int, int],
        tracks: list[TrackFeatures],
        template: SetTemplateDefinition,
        target_size: int,
    ) -> float:
        if not order:
            features = tracks[idx_map[candidate_id]]
            lufs = features.integrated_lufs if features.integrated_lufs is not None else -10.0
            bpm = features.bpm if features.bpm is not None else 130.0
            return max(0.0, 1.0 - ((lufs + 8.0) ** 2) / 36.0) + max(0.0, 1.0 - abs(bpm - 132) / 16)

        prev_id = order[-1]
        position = (len(order) - 1) / max(1, target_size - 2)
        context = build_pair_context(
            tracks[idx_map[prev_id]],
            tracks[idx_map[candidate_id]],
            position=position,
            template=template,
        )
        result = self.scorer.score(
            tracks[idx_map[prev_id]],
            tracks[idx_map[candidate_id]],
            intent=context.intent,
            section_context=context.section_context,
        )
        return float("-inf") if result.hard_reject else result.overall

    def _novelty_bonus(
        self,
        *,
        order: list[int],
        candidate_id: int,
        moods: dict[int, str | None] | None,
    ) -> float:
        if moods is None or not order:
            return 0.0
        candidate_mood = moods.get(candidate_id)
        if candidate_mood is None:
            return 0.0
        previous_mood = moods.get(order[-1])
        if previous_mood is None:
            return 0.0
        return 0.03 if previous_mood != candidate_mood else -0.02
