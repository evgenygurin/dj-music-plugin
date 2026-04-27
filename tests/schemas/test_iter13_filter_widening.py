"""Audit iter 13: batched widening of four more filter schemas
(systematic sweep instead of single-bug singletons).

* TrackFilter: sort_title__icontains
* SetVersionFilter: label__eq (only icontains existed)
* AudioFileFilter: bitrate (no lookups at all)
* TransitionHistoryFilter: overall_score__lte / range (only __gte)
"""

from __future__ import annotations

from app.schemas.audio_file import AudioFileFilter
from app.schemas.set import SetVersionFilter
from app.schemas.track import TrackFilter
from app.schemas.transition_history import TransitionHistoryFilter


def test_track_filter_accepts_sort_title_icontains() -> None:
    TrackFilter.model_validate({"sort_title__icontains": "heaven"})


def test_set_version_filter_accepts_label_eq() -> None:
    SetVersionFilter.model_validate({"label__eq": "v1"})


def test_audio_file_filter_accepts_bitrate_lookups() -> None:
    AudioFileFilter.model_validate({"bitrate__eq": 320})
    AudioFileFilter.model_validate({"bitrate__gte": 192})
    AudioFileFilter.model_validate({"bitrate__lte": 128})


def test_transition_history_filter_accepts_overall_score_lte_and_range() -> None:
    TransitionHistoryFilter.model_validate({"overall_score__lte": 0.5})
    TransitionHistoryFilter.model_validate({"overall_score__range": [0.6, 0.9]})
