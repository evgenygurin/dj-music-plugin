"""Fitness functions for set optimization.

Pure domain logic: no I/O, no DB, no async.
"""

from __future__ import annotations

import math

from app.domain.template.models import SetTemplateDefinition
from app.domain.transition.pair_context import build_pair_context
from app.domain.transition.scorer import TransitionScorer
from app.shared.features import TrackFeatures

_FITNESS_WEIGHTS = {
    "transition": 0.35,
    "bpm_smooth": 0.20,
    "energy_arc": 0.20,
    "variety": 0.10,
    "template": 0.15,
}


def transition_quality(
    scorer: TransitionScorer,
    tracks: list[TrackFeatures],
    order: list[int],
    idx_map: dict[int, int],
    template: SetTemplateDefinition | None = None,
    score_cache: dict[tuple[int, int, str, str | None], float] | None = None,
    reject_mask: set[tuple[int, int]] | None = None,
) -> float:
    """Average transition score across consecutive pairs, using intent-aware weights.

    Two-stage cost cut:

    * ``reject_mask`` (set of ``(idx_a, idx_b)`` known to fail
      ``check_hard_constraints``) lets us skip the full ``scorer.score``
      call for pairs that were screened out by a cheap up-front
      O(N²) scan. Hard-rejected pairs contribute ``0.0`` without ever
      touching the heavy stem-aware scoring path.
    * ``score_cache`` keyed by ``(idx_a, idx_b, intent.value)`` memoises
      the surviving pairs across hundreds of GA fitness evaluations.
      Same pair, same intent → cache hit, no second compute.

    Together: a 200-track pool with ~80 % hard-reject rate goes from
    ~3.98 M scorer.score calls to ~8 k actual computes.
    """
    if len(order) < 2:
        return 1.0
    total = 0.0
    n = len(order)
    for i in range(n - 1):
        idx_a = idx_map[order[i]]
        idx_b = idx_map[order[i + 1]]

        # Stage 1: cheap mask lookup. Hard-rejected pairs cost nothing
        # past this point — fitness gradient still penalises them via
        # the +0.0 contribution.
        if reject_mask is not None and (idx_a, idx_b) in reject_mask:
            continue

        a = tracks[idx_a]
        b = tracks[idx_b]
        position = i / max(1, n - 2)
        context = build_pair_context(a, b, position=position, template=template)
        pair_class = (
            context.section_context.section_pair_class.value
            if context.section_context is not None
            else None
        )

        # Stage 2: memoised scorer.score for surviving pairs.
        if score_cache is not None:
            key = (idx_a, idx_b, context.intent.value, pair_class)
            cached = score_cache.get(key)
            if cached is None:
                score = scorer.score(
                    a,
                    b,
                    intent=context.intent,
                    section_context=context.section_context,
                )
                cached = 0.0 if score.hard_reject else score.overall
                score_cache[key] = cached
            total += cached
        else:
            score = scorer.score(
                a,
                b,
                intent=context.intent,
                section_context=context.section_context,
            )
            total += 0.0 if score.hard_reject else score.overall
    return total / (n - 1)


def bpm_smoothness(
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
            total += math.exp(-(diff**2) / 32.0)
            count += 1
    return total / count if count > 0 else 0.5


def energy_arc_score(
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
        feat = tracks[idx_map[tid]]
        if feat.integrated_lufs is None:
            continue
        pos = i / (n - 1)
        ideal_peak_pos = 0.7
        arc = -(4.0 * (pos - ideal_peak_pos) ** 2) + 1.0
        ideal_lufs = -14.0 + arc * 8.0
        diff = abs(feat.integrated_lufs - ideal_lufs)
        total += math.exp(-(diff**2) / 18.0)
    return total / n


def subgenre_variety(
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
    return min(1.0, len(unique) / 4.0)


def template_fitness(
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
        track_idx = min(n - 1, max(0, int(slot.position * n)))
        tid = order[track_idx]
        feat = tracks[idx_map[tid]]

        score = 0.0
        components = 0

        if feat.bpm is not None:
            if slot.bpm_min <= feat.bpm <= slot.bpm_max:
                score += 1.0
            else:
                dist = min(abs(feat.bpm - slot.bpm_min), abs(feat.bpm - slot.bpm_max))
                score += max(0.0, 1.0 - dist / 10.0)
            components += 1

        if feat.integrated_lufs is not None:
            lufs_diff = abs(feat.integrated_lufs - slot.energy_lufs)
            score += math.exp(-(lufs_diff**2) / 8.0)
            components += 1

        if moods and slot.target_mood is not None:
            track_mood = moods.get(tid)
            if track_mood == slot.target_mood:
                score += 1.0
            elif track_mood is not None:
                score += 0.3
            components += 1

        if components > 0:
            slot_score = score / components
            slot_score = slot_score * (1.0 - slot.flexibility) + slot.flexibility
            total += slot_score
        slot_count += 1

    return total / slot_count if slot_count > 0 else 0.5


def compute_fitness(
    scorer: TransitionScorer,
    tracks: list[TrackFeatures],
    order: list[int],
    idx_map: dict[int, int],
    template: SetTemplateDefinition | None = None,
    moods: dict[int, str | None] | None = None,
    score_cache: dict[tuple[int, int, str, str | None], float] | None = None,
    reject_mask: set[tuple[int, int]] | None = None,
) -> float:
    """Weighted fitness for a track ordering. Returns 0-1.

    ``reject_mask`` and ``score_cache`` are forwarded to
    ``transition_quality`` for the two-stage memoisation described in
    its docstring. Both should be created once per optimisation run by
    the caller and reused across every fitness evaluation.
    """
    w = _FITNESS_WEIGHTS

    trans = transition_quality(
        scorer,
        tracks,
        order,
        idx_map,
        template=template,
        score_cache=score_cache,
        reject_mask=reject_mask,
    )
    bpm = bpm_smoothness(tracks, order, idx_map)
    energy = energy_arc_score(tracks, order, idx_map)
    variety = subgenre_variety(tracks, order, idx_map, moods)

    if template is not None:
        tmpl = template_fitness(tracks, order, idx_map, template, moods)
        score = (
            w["transition"] * trans
            + w["bpm_smooth"] * bpm
            + w["energy_arc"] * energy
            + w["variety"] * variety
            + w["template"] * tmpl
        )
    else:
        base = 1.0 - w["template"]
        score = (
            (w["transition"] / base) * trans
            + (w["bpm_smooth"] / base) * bpm
            + (w["energy_arc"] / base) * energy
            + (w["variety"] / base) * variety
        )

    return score
