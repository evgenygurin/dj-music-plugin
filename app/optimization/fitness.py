"""Fitness functions for set optimization.

Pure domain logic: no I/O, no DB, no async.
"""

from __future__ import annotations

import math

from app.core.track_features import TrackFeatures
from app.templates.models import SetTemplateDefinition
from app.transition.intent import infer_intent
from app.transition.scorer import TransitionScorer

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
) -> float:
    """Average transition score across consecutive pairs, using intent-aware weights."""
    if len(order) < 2:
        return 1.0
    total = 0.0
    n = len(order)
    for i in range(n - 1):
        a = tracks[idx_map[order[i]]]
        b = tracks[idx_map[order[i + 1]]]
        position = i / max(1, n - 2)
        energy_delta = (b.integrated_lufs or -8.0) - (a.integrated_lufs or -8.0)
        intent = infer_intent(position, energy_delta)
        score = scorer.score(a, b, intent=intent)
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
        t = tracks[idx_map[tid]]
        if t.integrated_lufs is None:
            continue
        pos = i / (n - 1)
        ideal_peak_pos = 0.7
        arc = -(4.0 * (pos - ideal_peak_pos) ** 2) + 1.0
        ideal_lufs = -14.0 + arc * 8.0
        diff = abs(t.integrated_lufs - ideal_lufs)
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
        t = tracks[idx_map[tid]]

        score = 0.0
        components = 0

        if t.bpm is not None:
            if slot.bpm_min <= t.bpm <= slot.bpm_max:
                score += 1.0
            else:
                dist = min(abs(t.bpm - slot.bpm_min), abs(t.bpm - slot.bpm_max))
                score += max(0.0, 1.0 - dist / 10.0)
            components += 1

        if t.integrated_lufs is not None:
            lufs_diff = abs(t.integrated_lufs - slot.energy_lufs)
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
) -> float:
    """Weighted fitness for a track ordering. Returns 0-1."""
    w = _FITNESS_WEIGHTS

    trans = transition_quality(scorer, tracks, order, idx_map)
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
