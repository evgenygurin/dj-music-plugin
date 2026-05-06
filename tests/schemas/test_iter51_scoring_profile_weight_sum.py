"""Audit iter 51 (T-49): ``ScoringProfileCreate`` and
``ScoringProfileUpdate`` accepted weights that didn't sum to 1.0.
The 6 component weights are convex-combination weights — anything
other than sum=1.0 produces out-of-range scores when applied.

Live confirmation:

    entity_create(scoring_profile, {"name":"bad-weights",
                                    "bpm_weight":0.5, "harmonics_weight":0.5,
                                    ...all 0.5})
    -> 200 OK (profile persists with sum=3.0)

Now schema-level ``model_validator`` rejects weights whose sum is
outside ``[1.0 - 0.001, 1.0 + 0.001]``. Update is checked only
when ALL 6 weights are supplied (partial patches can't enforce
the cross-row invariant without a DB read).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.scoring_profile import ScoringProfileCreate, ScoringProfileUpdate

_DEFAULT_VALID = {
    "name": "x",
    "bpm_weight": 0.20,
    "harmonics_weight": 0.12,
    "energy_weight": 0.18,
    "bass_weight": 0.20,
    "drums_weight": 0.15,
    "vocals_weight": 0.15,
}


class TestScoringProfileCreateWeightSum:
    def test_default_weights_accepted(self) -> None:
        """Sum=1.00 (default DJ-Music weights) → OK."""
        c = ScoringProfileCreate.model_validate(_DEFAULT_VALID)
        assert c.bpm_weight == 0.20

    def test_uniform_05_rejected(self) -> None:
        """Sum=3.00 → fail."""
        bad = dict(_DEFAULT_VALID)
        bad.update(
            {
                f: 0.5
                for f in (
                    "bpm_weight",
                    "harmonics_weight",
                    "energy_weight",
                    "bass_weight",
                    "drums_weight",
                    "vocals_weight",
                )
            }
        )
        with pytest.raises(ValidationError, match=r"weights must sum to 1\.0"):
            ScoringProfileCreate.model_validate(bad)

    def test_below_threshold_rejected(self) -> None:
        """Sum=0.5 → fail."""
        bad = dict(_DEFAULT_VALID)
        bad.update(
            {
                f: 0.083
                for f in (
                    "bpm_weight",
                    "harmonics_weight",
                    "energy_weight",
                    "bass_weight",
                    "drums_weight",
                    "vocals_weight",
                )
            }
        )
        with pytest.raises(ValidationError, match=r"weights must sum to 1\.0"):
            ScoringProfileCreate.model_validate(bad)

    def test_within_epsilon_accepted(self) -> None:
        """Float drift within 0.001 → OK."""
        # Sum = 0.20 + 0.12 + 0.18 + 0.20 + 0.15 + 0.15 = 1.0000…
        # nudge timbral by +0.0005 → sum = 1.0005 → still within eps
        almost = dict(_DEFAULT_VALID)
        almost["vocals_weight"] = 0.1505
        ScoringProfileCreate.model_validate(almost)

    def test_outside_epsilon_rejected(self) -> None:
        """Sum=1.01 (outside ±0.001) → fail."""
        almost = dict(_DEFAULT_VALID)
        almost["vocals_weight"] = 0.16  # sum = 1.01
        with pytest.raises(ValidationError, match=r"weights must sum to 1\.0"):
            ScoringProfileCreate.model_validate(almost)


class TestScoringProfileUpdateWeightSum:
    def test_full_six_weight_update_validated(self) -> None:
        """All 6 supplied → enforce sum invariant."""
        bad = {
            f: 0.5
            for f in (
                "bpm_weight",
                "harmonics_weight",
                "energy_weight",
                "bass_weight",
                "drums_weight",
                "vocals_weight",
            )
        }
        with pytest.raises(ValidationError, match=r"weights must sum to 1\.0"):
            ScoringProfileUpdate.model_validate(bad)

    def test_full_six_valid_update_accepted(self) -> None:
        ScoringProfileUpdate.model_validate(
            {
                "bpm_weight": 0.20,
                "harmonics_weight": 0.12,
                "energy_weight": 0.18,
                "bass_weight": 0.20,
                "drums_weight": 0.15,
                "vocals_weight": 0.15,
            }
        )

    def test_partial_update_skipped(self) -> None:
        """Single-weight patch passes (sum invariant can't be checked
        without the existing row's other 5 weights)."""
        ScoringProfileUpdate.model_validate({"bpm_weight": 0.99})
        ScoringProfileUpdate.model_validate({"bpm_weight": 0.5, "harmonics_weight": 0.5})

    def test_description_only_accepted(self) -> None:
        ScoringProfileUpdate.model_validate({"description": "tweaked"})
