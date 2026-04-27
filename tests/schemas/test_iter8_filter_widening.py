"""Audit iter 8: three more filter schemas underspec'd vs canonical
queries (same class as Bug A from v1.2.0).

* ``SetVersionFilter`` rejected ``quality_score__gte``.
* ``AudioFileFilter`` rejected ``file_size__gte``.
* ``TransitionView`` was missing ``reject_reason`` even though the
  ORM column exists and ``local://transition/.../score`` returns it -
  ``entity_get(transition, id)`` couldn't tell consumers WHY a pair
  was rejected.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.audio_file import AudioFileFilter
from app.schemas.set import SetVersionFilter
from app.schemas.transition import TransitionView


def test_set_version_filter_accepts_quality_lookups() -> None:
    SetVersionFilter.model_validate({"quality_score__gte": 0.7})
    SetVersionFilter.model_validate({"quality_score__lte": 0.5})
    SetVersionFilter.model_validate({"quality_score__range": [0.6, 0.9]})


def test_set_version_filter_still_rejects_garbage() -> None:
    with pytest.raises(ValidationError):
        SetVersionFilter.model_validate({"bogus": 1})


def test_audio_file_filter_accepts_file_size_lookups() -> None:
    AudioFileFilter.model_validate({"file_size__gte": 1_000_000})
    AudioFileFilter.model_validate({"file_size__lte": 10_000_000})
    AudioFileFilter.model_validate({"file_size__range": [1_000_000, 50_000_000]})


def test_transition_view_includes_reject_reason() -> None:
    """``entity_get(transition, id)`` should expose ``reject_reason``
    so consumers can read WHY a pair was hard-rejected without going
    through the resource layer."""
    assert "reject_reason" in TransitionView.model_fields
