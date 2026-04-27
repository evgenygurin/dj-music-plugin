"""Audit iter 7: ``TransitionFilter`` rejected ``hard_reject__eq``,
the canonical "show me hard-reject transitions" query.

Same class as Bug A: declared lookups < documented contract.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.transition import TransitionFilter


@pytest.mark.parametrize(
    "lookup,value",
    [
        ("hard_reject__eq", True),
        ("hard_reject__eq", False),
        ("overall_quality__range", [0.6, 0.9]),
    ],
)
def test_transition_filter_accepts_new_lookups(lookup: str, value: object) -> None:
    TransitionFilter.model_validate({lookup: value})


def test_transition_filter_still_rejects_garbage() -> None:
    with pytest.raises(ValidationError):
        TransitionFilter.model_validate({"bogus": 1})
