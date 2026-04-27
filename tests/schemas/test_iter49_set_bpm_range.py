"""Audit iter 49 (T-47): ``SetCreate`` and ``SetUpdate`` accepted
``target_bpm_min > target_bpm_max`` — a logically impossible range
that any downstream "in target range" query treats as
"match nothing" silently.

Live confirmation:

    entity_create(set, {"name":"T","target_bpm_min":130,"target_bpm_max":120})
    -> 200 OK (set 49 created with min=130, max=120)

Now ``model_validator(mode="after")`` rejects the inversion at
schema-validation time. Pure-payload only — partial updates that
supply just one side cannot enforce the cross-row invariant
without a DB read; the dispatcher remains responsible for that.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.set import SetCreate, SetUpdate


class TestSetCreateBpmRange:
    def test_min_gt_max_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"target_bpm_min .* must be <="):
            SetCreate.model_validate({"name": "T", "target_bpm_min": 130, "target_bpm_max": 120})

    def test_min_eq_max_accepted(self) -> None:
        """Equal endpoints are a valid (singleton) range."""
        c = SetCreate.model_validate({"name": "T", "target_bpm_min": 128, "target_bpm_max": 128})
        assert c.target_bpm_min == 128 == c.target_bpm_max

    def test_min_lt_max_accepted(self) -> None:
        c = SetCreate.model_validate({"name": "T", "target_bpm_min": 120, "target_bpm_max": 130})
        assert c.target_bpm_min < c.target_bpm_max

    def test_only_min_supplied_accepted(self) -> None:
        """Half-open ranges pass validation — caller may want
        unbounded upper limit."""
        SetCreate.model_validate({"name": "T", "target_bpm_min": 120})

    def test_only_max_supplied_accepted(self) -> None:
        SetCreate.model_validate({"name": "T", "target_bpm_max": 130})

    def test_neither_supplied_accepted(self) -> None:
        SetCreate.model_validate({"name": "T"})


class TestSetUpdateBpmRange:
    def test_min_gt_max_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"target_bpm_min .* must be <="):
            SetUpdate.model_validate({"target_bpm_min": 140, "target_bpm_max": 130})

    def test_only_one_side_accepted(self) -> None:
        """Patch-style update with one side must pass (the other side
        stays untouched on the row)."""
        SetUpdate.model_validate({"target_bpm_min": 120})
        SetUpdate.model_validate({"target_bpm_max": 140})

    def test_valid_range_accepted(self) -> None:
        SetUpdate.model_validate({"target_bpm_min": 120, "target_bpm_max": 140})
