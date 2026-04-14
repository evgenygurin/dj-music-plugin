"""Harmonic (key) compatibility scoring.

Camelot wheel distance, weighted by HNR and chroma quality, optionally
blended with Tonnetz cosine similarity for a continuous estimate.
"""

from __future__ import annotations

from app.camelot.wheel import camelot_distance
from app.entities.audio.features import TrackFeatures
from app.transition.constants import (
    ATONAL_RELAX_FLOOR,
    CAMELOT_BASE_SCORES,
    DRUM_ONLY_HARMONIC_FLOOR,
    HNR_NORM_FLOOR,
    HNR_NORM_HIGH_DB,
    HNR_NORM_LOW_DB,
    KEY_CONFIDENCE_BLEND_THRESHOLD,
    TONNETZ_BLEND,
)
from app.transition.math_helpers import cosine_similarity
from app.transition.section_context import SectionContext


def score_harmonic(
    from_t: TrackFeatures,
    to_t: TrackFeatures,
    *,
    section_context: SectionContext | None = None,
) -> float:
    """Score harmonic compatibility. Range [0, 1].

    When ``section_context`` is provided and both the mix-out and
    mix-in windows fall on percussion-only sections
    (intro/outro/sustain/ambient), the score is floored at
    ``DRUM_ONLY_HARMONIC_FLOOR`` — Pioneer DJ blog and Vande Veire &
    De Bie (JASMP 2018) both note that key compatibility loses
    perceptual relevance on drum-only material.
    """
    if from_t.key_code is None or to_t.key_code is None:
        return 0.5
    dist = camelot_distance(from_t.key_code, to_t.key_code)
    base = CAMELOT_BASE_SCORES.get(dist, 0.0)

    # Both atonal tracks → key less important, relax to at least the floor
    if from_t.atonality is True and to_t.atonality is True:
        base = max(ATONAL_RELAX_FLOOR, base)

    # Weight by HNR (linear normalize from -30..0 dB → floor..1.0)
    hnr_factor = 1.0
    if from_t.hnr_db is not None and to_t.hnr_db is not None:
        avg_hnr = (from_t.hnr_db + to_t.hnr_db) / 2
        span = HNR_NORM_HIGH_DB - HNR_NORM_LOW_DB
        normalized = (avg_hnr - HNR_NORM_LOW_DB) / span if span else 1.0
        hnr_factor = max(HNR_NORM_FLOOR, min(1.0, normalized))

    score = base * hnr_factor

    # Tonnetz cosine similarity blended with Camelot base
    if from_t.tonnetz_vector and to_t.tonnetz_vector:
        tonnetz_cos = cosine_similarity(from_t.tonnetz_vector, to_t.tonnetz_vector)
        score = (1.0 - TONNETZ_BLEND) * score + TONNETZ_BLEND * tonnetz_cos

    # Key confidence: low confidence → blend toward neutral (0.5)
    if from_t.key_confidence is not None and to_t.key_confidence is not None:
        min_conf = min(from_t.key_confidence, to_t.key_confidence)
        if min_conf < KEY_CONFIDENCE_BLEND_THRESHOLD:
            blend = min_conf / KEY_CONFIDENCE_BLEND_THRESHOLD
            score = score * blend + 0.5 * (1.0 - blend)

    # Section-aware relaxation: drum-only mix region → harmonic floor.
    if section_context is not None and section_context.is_drum_only_pair:
        score = max(score, DRUM_ONLY_HARMONIC_FLOOR)

    return score
