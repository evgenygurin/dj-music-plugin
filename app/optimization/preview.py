"""Pure preview logic for set arc evaluation.

No I/O, no DB, no async. Given a dict of TrackFeatures and an ordered
list of track IDs, computes fitness, per-position arcs, and identifies
weak transition spots.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.entities.audio.features import TrackFeatures
from app.optimization.fitness import compute_fitness
from app.templates.models import SetTemplateDefinition
from app.transition.scorer import TransitionScorer

_WEAK_SPOT_THRESHOLD = 0.45


@dataclass
class PreviewResult:
    """Result of a non-destructive set arc preview."""

    score: float
    energy_arc: list[float]
    bpm_arc: list[float]
    weak_spots: list[int]
    recommendation: str
    missing_track_ids: list[int] = field(default_factory=list)


def preview_arc(
    scorer: TransitionScorer,
    features_map: dict[int, TrackFeatures],
    track_ids: list[int],
    template: SetTemplateDefinition | None = None,
    moods: dict[int, str | None] | None = None,
) -> PreviewResult:
    """Evaluate a specific track ordering without saving anything.

    Args:
        scorer: Initialized TransitionScorer.
        features_map: Mapping of track_id → TrackFeatures.
        track_ids: Ordered list of track IDs to evaluate.
        template: Optional template definition for template_fitness scoring.
        moods: Optional external mood overrides keyed by track_id.

    Returns:
        PreviewResult with fitness score, arcs, weak spots, and recommendation.
    """
    valid_ids = [tid for tid in track_ids if tid in features_map]
    missing = [tid for tid in track_ids if tid not in features_map]

    if len(valid_ids) <= 1:
        return PreviewResult(
            score=1.0,
            energy_arc=[features_map[valid_ids[0]].integrated_lufs or 0.0] if valid_ids else [],
            bpm_arc=[features_map[valid_ids[0]].bpm or 0.0] if valid_ids else [],
            weak_spots=[],
            recommendation="Only one track — no transitions to evaluate.",
            missing_track_ids=missing,
        )

    tracks = [features_map[tid] for tid in valid_ids]
    # order and idx_map use positional indices: order[i] == i, idx_map[i] == i
    order = list(range(len(valid_ids)))
    idx_map = {i: i for i in range(len(valid_ids))}

    positional_moods: dict[int, str | None] | None = None
    if moods:
        positional_moods = {i: moods.get(tid) for i, tid in enumerate(valid_ids)}

    score = compute_fitness(
        scorer, tracks, order, idx_map, template=template, moods=positional_moods
    )

    energy_arc = [t.integrated_lufs if t.integrated_lufs is not None else 0.0 for t in tracks]
    bpm_arc = [t.bpm if t.bpm is not None else 0.0 for t in tracks]

    weak_spots = _find_weak_spots(scorer, tracks)

    recommendation = _build_recommendation(score, weak_spots, missing, len(valid_ids))

    return PreviewResult(
        score=round(score, 3),
        energy_arc=energy_arc,
        bpm_arc=bpm_arc,
        weak_spots=weak_spots,
        recommendation=recommendation,
        missing_track_ids=missing,
    )


def _find_weak_spots(
    scorer: TransitionScorer,
    tracks: list[TrackFeatures],
) -> list[int]:
    """Return 0-based positions (of the outgoing track) where transition score < threshold."""
    weak: list[int] = []
    for i in range(len(tracks) - 1):
        result = scorer.score(tracks[i], tracks[i + 1])
        transition_score = 0.01 if result.hard_reject else result.overall
        if transition_score < _WEAK_SPOT_THRESHOLD:
            weak.append(i)
    return weak


def _build_recommendation(
    score: float,
    weak_spots: list[int],
    missing: list[int],
    n_tracks: int,
) -> str:
    """Build a plain-language recommendation string."""
    parts: list[str] = []

    if score >= 0.75:
        parts.append(f"Strong set arc (score {score:.2f}).")
    elif score >= 0.55:
        parts.append(f"Decent arc (score {score:.2f}) — room for improvement.")
    else:
        parts.append(f"Weak arc (score {score:.2f}) — significant transition problems.")

    if weak_spots:
        positions = ", ".join(str(p + 1) for p in weak_spots)
        parts.append(
            f"Weak transition{'s' if len(weak_spots) > 1 else ''} after "
            f"position{'s' if len(weak_spots) > 1 else ''} {positions}."
        )
    else:
        parts.append("All transitions within acceptable range.")

    if missing:
        parts.append(
            f"{len(missing)} track{'s' if len(missing) > 1 else ''} "
            f"had no features and were excluded."
        )

    return " ".join(parts)
