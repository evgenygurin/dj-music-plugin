from app.core.schemas import (
    PaginatedResponse,
    PlaylistSummary,
    SetSummary,
    TrackBrief,
    TrackStandard,
)


def test_track_brief() -> None:
    t = TrackBrief(
        id=1,
        title="X",
        artist_names=["A"],
        bpm=128.0,
        key_camelot="8A",
        duration_ms=300000,
    )
    assert t.id == 1 and t.bpm == 128.0


def test_track_standard_extends_brief() -> None:
    t = TrackStandard(
        id=1,
        title="X",
        artist_names=["A"],
        energy_lufs=-8.0,
        mood="driving",
    )
    assert t.energy_lufs == -8.0 and t.has_features is False


def test_playlist_summary() -> None:
    p = PlaylistSummary(id=1, name="Techno", track_count=50)
    assert p.track_count == 50


def test_set_summary() -> None:
    s = SetSummary(id=1, name="Peak Hour", latest_score=0.82)
    assert s.latest_score == 0.82


def test_paginated_response() -> None:
    r = PaginatedResponse[TrackBrief](items=[], total=0)
    assert r.next_cursor is None
