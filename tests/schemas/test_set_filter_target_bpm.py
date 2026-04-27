"""Audit iter 17: ``SetFilter`` rejected target_bpm_min/max + duration
range lookups despite the ``SetView`` declaring all three columns."""

from __future__ import annotations

from app.schemas.set import SetFilter


def test_set_filter_accepts_target_bpm_lookups() -> None:
    SetFilter.model_validate({"target_bpm_min__gte": 120})
    SetFilter.model_validate({"target_bpm_max__lte": 145})


def test_set_filter_accepts_target_duration_lookups() -> None:
    SetFilter.model_validate({"target_duration_ms__gte": 3_600_000})
    SetFilter.model_validate({"target_duration_ms__lte": 7_200_000})
