"""Audit iter 19: 3 more filter widenings.

* AudioFileFilter: sample_rate (eq, in) + channels (eq).
* TransitionFilter: reject_reason (icontains, isnull) for "find
  all pairs rejected because of BPM diff" queries.
"""

from __future__ import annotations

from app.schemas.audio_file import AudioFileFilter
from app.schemas.transition import TransitionFilter


def test_audio_file_filter_accepts_sample_rate_lookups() -> None:
    AudioFileFilter.model_validate({"sample_rate__eq": 44100})
    AudioFileFilter.model_validate({"sample_rate__in": [44100, 48000]})


def test_audio_file_filter_accepts_channels_lookup() -> None:
    AudioFileFilter.model_validate({"channels__eq": 2})


def test_transition_filter_accepts_reject_reason_lookups() -> None:
    TransitionFilter.model_validate({"reject_reason__icontains": "BPM"})
    TransitionFilter.model_validate({"reject_reason__isnull": True})
