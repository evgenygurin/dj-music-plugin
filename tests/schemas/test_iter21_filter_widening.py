"""Audit iter 21: TransitionHistoryFilter.style + PlaylistFilter.name__startswith."""

from __future__ import annotations

from app.schemas.playlist import PlaylistFilter
from app.schemas.transition_history import TransitionHistoryFilter


def test_transition_history_filter_accepts_style_lookups() -> None:
    TransitionHistoryFilter.model_validate({"style__eq": "bass_swap_short"})
    TransitionHistoryFilter.model_validate({"style__in": ["long_blend", "echo_out"]})
    TransitionHistoryFilter.model_validate({"style__icontains": "blend"})


def test_playlist_filter_accepts_name_startswith() -> None:
    PlaylistFilter.model_validate({"name__startswith": "Subgenre"})
