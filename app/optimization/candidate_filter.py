"""Pre-filter track candidates by hard constraints before full transition scoring.

Builds an adjacency list (graph) mapping each track_id to the set of valid
next-track candidates. A pair is valid if it passes all three hard constraints:
BPM diff ≤ threshold, Camelot distance < threshold, LUFS gap ≤ threshold.

When a feature value is None the corresponding constraint is skipped (can't
reject what we can't measure).
"""

from __future__ import annotations

from app.camelot.wheel import camelot_distance
from app.config import settings
from app.entities.audio.features import TrackFeatures
from app.transition.math_helpers import bpm_distance


def build_adjacency(
    features: dict[int, TrackFeatures],
) -> dict[int, set[int]]:
    """Pre-compute valid next-track candidates for each track.

    Args:
        features: Mapping of track_id → TrackFeatures.

    Returns:
        Adjacency list: track_id → set of valid successor track_ids.
        Every track_id from ``features`` appears as a key.
    """
    ids = list(features.keys())
    graph: dict[int, set[int]] = {tid: set() for tid in ids}

    for a_id in ids:
        feat_a = features[a_id]
        for b_id in ids:
            if b_id == a_id:
                continue
            feat_b = features[b_id]
            if not _passes_hard_constraints(feat_a, feat_b):
                continue
            graph[a_id].add(b_id)

    return graph


def _passes_hard_constraints(a: TrackFeatures, b: TrackFeatures) -> bool:
    """Return True if the pair survives all hard constraints."""
    # BPM
    if a.bpm is not None and b.bpm is not None:
        delta_bpm = bpm_distance(a.bpm, b.bpm)
        if delta_bpm > settings.transition_hard_reject_bpm_diff:
            return False

    # Camelot / key
    if a.key_code is not None and b.key_code is not None:
        dist = camelot_distance(a.key_code, b.key_code)
        if dist >= settings.transition_hard_reject_camelot_dist:
            return False

    # LUFS energy gap
    if a.integrated_lufs is not None and b.integrated_lufs is not None:
        gap = abs(a.integrated_lufs - b.integrated_lufs)
        if gap > settings.transition_hard_reject_energy_gap:
            return False

    return True
