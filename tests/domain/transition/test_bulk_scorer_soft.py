"""Soft Camelot mode must drop only the key mask from vectorised hard-rejects.

``hard_reject_mask_bulk(..., soft_camelot=True)`` is the bulk twin of
``check_hard_constraints(..., soft_camelot=True)``: a reliable-key
Camelot distance >= ``hard_reject_camelot_dist`` no longer rejects the
pair, while BPM/LUFS gates stay active. ``score_pairs_bulk`` forwards
the flag so a soft pair gets a non-zero overall instead of the 0.0
clamp.
"""

from __future__ import annotations

import numpy as np

from app.domain.transition.bulk_scorer import (
    extract_feature_arrays,
    hard_reject_mask_bulk,
    score_pairs_bulk,
)
from app.domain.transition.intent import TransitionIntent
from app.shared.features import TrackFeatures


def _tracks() -> list[TrackFeatures]:
    # (0, 12) is a reliable-key Camelot distance >= 5 pair (key_confidence
    # 0.9 > hard_reject_key_confidence_floor, atonality False).
    return [
        TrackFeatures(bpm=130.0, key_code=0, key_confidence=0.9, integrated_lufs=-10.0),
        TrackFeatures(bpm=130.0, key_code=12, key_confidence=0.9, integrated_lufs=-10.0),
        TrackFeatures(bpm=130.0, key_code=12, key_confidence=0.9, integrated_lufs=-10.0),
    ]


def test_soft_mask_drops_camelot_keeps_compatible() -> None:
    fa = extract_feature_arrays(_tracks())
    ia = np.array([0], dtype=np.int64)
    ib = np.array([1], dtype=np.int64)

    assert hard_reject_mask_bulk(fa, ia, ib)[0] == True  # noqa: E712
    assert hard_reject_mask_bulk(fa, ia, ib, soft_camelot=True)[0] == False  # noqa: E712


def test_soft_mask_keeps_bpm_reject() -> None:
    fa = extract_feature_arrays(
        [
            TrackFeatures(bpm=120.0, key_code=8, key_confidence=0.9, integrated_lufs=-10.0),
            TrackFeatures(bpm=140.0, key_code=8, key_confidence=0.9, integrated_lufs=-10.0),
        ]
    )
    ia = np.array([0], dtype=np.int64)
    ib = np.array([1], dtype=np.int64)
    assert hard_reject_mask_bulk(fa, ia, ib, soft_camelot=True)[0] == True  # noqa: E712


def test_score_pairs_bulk_soft_scores_camelot_pair() -> None:
    fa = extract_feature_arrays(_tracks())
    pairs = [(0, 1)]
    strict = score_pairs_bulk(fa, pairs, [TransitionIntent.MAINTAIN])
    soft = score_pairs_bulk(fa, pairs, [TransitionIntent.MAINTAIN], soft_camelot=True)
    key = (0, 1, TransitionIntent.MAINTAIN.value)
    assert strict[key] == 0.0
    assert soft[key] > 0.0
