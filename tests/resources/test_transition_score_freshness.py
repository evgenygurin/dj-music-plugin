"""Regression: ``local://transition/{a}/{b}/score`` must always recompute.

Audit (2026-04-27, Bug C) caught the resource reading from the
``transitions`` table first and only falling back to live compute on
miss. The persisted row could be stale — written by a prior
``set_version_build`` against features that have since been
re-analyzed at a higher level — producing ``hard_reject=true`` while
the live values cleanly pass all hard constraints. Two endpoints
disagreed about the same pair (``/score`` returned the stale 0,
``/explain`` returned a real 0.78), breaking user trust.

Fix strategy: stop reading persisted rows in the standalone resource.
``TransitionScorer`` is pure-domain compute (~1 ms), so the cache hit
isn't worth the staleness risk. The ``transitions`` table remains
write-only for set composition history.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.resources.transition import transition_score


@pytest.mark.asyncio
async def test_transition_score_does_not_consult_persisted_table() -> None:
    """The persisted-first short-circuit was the staleness bug — drop it.

    Mock UoW that would happily hand out a stale persisted row and
    still verify ``get_by_pair`` was NEVER awaited. ``_load_features_pair``
    is the new sole entry point.
    """
    stale = MagicMock(
        overall_quality=0.0,
        hard_reject=True,
        reject_reason="stale: was written when features differed",
        bpm_score=0.0,
        harmonic_score=0.0,
        energy_score=0.0,
        spectral_score=0.0,
        groove_score=0.0,
        timbral_score=0.0,
    )
    uow = MagicMock()
    uow.transitions = MagicMock()
    uow.transitions.get_by_pair = AsyncMock(return_value=stale)
    uow.transitions.get_pair = AsyncMock(return_value=stale)

    # Provide live feature values that score WELL — same key, same BPM.
    live = MagicMock(
        bpm=128.0,
        bpm_confidence=1.0,
        bpm_stability=1.0,
        variable_tempo=False,
        key_code=14,
        key_confidence=1.0,
        atonality=False,
        hnr_db=0.0,
        chroma_entropy=0.0,
        tonnetz_vector=None,
        integrated_lufs=-12.0,
        loudness_range_lu=8.0,
        crest_factor_db=10.0,
        energy_slope=0.0,
        mfcc_vector=None,
        spectral_centroid_hz=2000.0,
        energy_bands=None,
        spectral_rolloff_85=4000.0,
        spectral_rolloff_95=6000.0,
        spectral_slope=0.0,
        spectral_flux_std=1.0,
        dissonance_mean=0.0,
        spectral_complexity_mean=10.0,
        onset_rate=4.0,
        kick_prominence=0.6,
        beat_loudness_band_ratio=None,
        pulse_clarity=0.5,
        hp_ratio=2.0,
        tempogram_ratio_vector=None,
        spectral_contrast=10.0,
        pitch_salience_mean=0.3,
        danceability=2.0,
        dynamic_complexity=0.3,
    )
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={1: live, 2: live})

    payload = json.loads(await transition_score(from_id=1, to_id=2, uow=uow))

    # The persisted row should never have been consulted.
    uow.transitions.get_by_pair.assert_not_called()
    uow.transitions.get_pair.assert_not_called()
    # Live compute on identical features → not hard-rejected.
    assert payload["hard_reject"] is False, payload
    assert payload["overall"] > 0.0, payload


@pytest.mark.asyncio
async def test_transition_score_and_explain_agree_on_overall() -> None:
    """Score and explain compute the same value off the same inputs."""
    from app.resources.transition import transition_explain

    live = MagicMock(
        bpm=128.0,
        bpm_confidence=1.0,
        bpm_stability=1.0,
        variable_tempo=False,
        key_code=14,
        key_confidence=1.0,
        atonality=False,
        hnr_db=0.0,
        chroma_entropy=0.0,
        tonnetz_vector=None,
        integrated_lufs=-12.0,
        loudness_range_lu=8.0,
        crest_factor_db=10.0,
        energy_slope=0.0,
        mfcc_vector=None,
        spectral_centroid_hz=2000.0,
        energy_bands=None,
        spectral_rolloff_85=4000.0,
        spectral_rolloff_95=6000.0,
        spectral_slope=0.0,
        spectral_flux_std=1.0,
        dissonance_mean=0.0,
        spectral_complexity_mean=10.0,
        onset_rate=4.0,
        kick_prominence=0.6,
        beat_loudness_band_ratio=None,
        pulse_clarity=0.5,
        hp_ratio=2.0,
        tempogram_ratio_vector=None,
        spectral_contrast=10.0,
        pitch_salience_mean=0.3,
        danceability=2.0,
        dynamic_complexity=0.3,
    )
    uow = MagicMock()
    uow.transitions = MagicMock()
    uow.transitions.get_by_pair = AsyncMock(
        return_value=MagicMock(
            overall_quality=0.0,
            hard_reject=True,
            reject_reason="stale",
            bpm_score=0.0,
            harmonic_score=0.0,
            energy_score=0.0,
            spectral_score=0.0,
            groove_score=0.0,
            timbral_score=0.0,
        )
    )
    uow.track_features = MagicMock()
    uow.track_features.get_scoring_features_batch = AsyncMock(return_value={1: live, 2: live})

    score_payload = json.loads(await transition_score(from_id=1, to_id=2, uow=uow))
    explain_payload = json.loads(await transition_explain(from_id=1, to_id=2, uow=uow))
    assert abs(score_payload["overall"] - explain_payload["overall"]) < 1e-9, (
        score_payload,
        explain_payload,
    )
