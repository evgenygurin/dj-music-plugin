"""Audit iter 41 (T-39): closing the widening sweep on the last
two narrow entities — ``track_affinity`` and ``playlist``.

TrackAffinity:
* ``Filter`` only had 3 keys (``track_a_id__eq``,
  ``track_b_id__eq``, ``avg_score__gte``) — no id-range,
  no batch ``__in``, no ``__lte`` on score, and crucially no
  lookups on ``play_count`` / ``positive_count`` /
  ``negative_count`` even though those are how the affinity is
  computed and the canonical "popular pairs" / "all-positive
  feedback" queries depend on them.
* ``Update`` could only mutate ``avg_score`` and ``play_count`` —
  ``positive_count`` and ``negative_count`` had to be moved
  through the implicit refresh handler, blocking explicit
  recalibration.

Playlist:
* ``View`` dropped 2 persisted columns: ``source_app`` (which app
  produced the playlist — rekordbox / ym / serato) and
  ``platform_ids`` (JSON-encoded provider IDs needed for
  ``playlist_sync``).
* ``Filter`` rejected ``id__gt/gte/lt/lte`` (drift from
  ``set_version``) and lacked any lookups on the 2 newly-exposed
  columns.
* ``Create`` / ``Update`` couldn't write the same 2 columns —
  re-attaching a freshly-imported YM playlist to its bare-bones
  local twin required delete + recreate.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.playlist import (
    PlaylistCreate,
    PlaylistFilter,
    PlaylistUpdate,
    PlaylistView,
)
from app.schemas.track_affinity import TrackAffinityFilter, TrackAffinityUpdate


class TestTrackAffinityFilterIdAndBatch:
    @pytest.mark.parametrize("op", ["eq", "in", "gt", "gte", "lt", "lte"])
    def test_id_lookup(self, op: str) -> None:
        value = [1, 2, 3] if op == "in" else 42
        TrackAffinityFilter.model_validate({f"id__{op}": value})

    def test_track_a_id_in_accepted(self) -> None:
        TrackAffinityFilter.model_validate({"track_a_id__in": [1, 2, 3]})

    def test_track_b_id_in_accepted(self) -> None:
        TrackAffinityFilter.model_validate({"track_b_id__in": [10, 20]})


class TestTrackAffinityFilterScoreAndCounts:
    """Counter columns renamed in 2026-05-07 schema sync —
    ``positive_count``/``negative_count`` are now
    ``like_count``/``ban_count`` plus a fresh ``skip_count`` and a
    denormalised ``net_sentiment`` float."""

    def test_avg_score_lte_accepted(self) -> None:
        TrackAffinityFilter.model_validate({"avg_score__lte": 0.4})

    def test_avg_score_range_accepted(self) -> None:
        TrackAffinityFilter.model_validate({"avg_score__range": [0.3, 0.8]})

    @pytest.mark.parametrize("field", ["play_count", "like_count", "ban_count", "skip_count"])
    def test_count_lookup(self, field: str) -> None:
        TrackAffinityFilter.model_validate({f"{field}__gte": 5})
        TrackAffinityFilter.model_validate({f"{field}__lte": 100})

    def test_net_sentiment_range_accepted(self) -> None:
        TrackAffinityFilter.model_validate({"net_sentiment__range": [-0.5, 0.9]})


class TestTrackAffinityUpdate:
    def test_like_count_round_trips(self) -> None:
        upd = TrackAffinityUpdate.model_validate({"like_count": 7})
        assert upd.like_count == 7

    def test_ban_count_round_trips(self) -> None:
        upd = TrackAffinityUpdate.model_validate({"ban_count": 3})
        assert upd.ban_count == 3

    def test_ban_count_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            TrackAffinityUpdate.model_validate({"ban_count": -1})

    def test_net_sentiment_clamped_to_unit_range(self) -> None:
        with pytest.raises(ValidationError):
            TrackAffinityUpdate.model_validate({"net_sentiment": 1.5})
        upd = TrackAffinityUpdate.model_validate({"net_sentiment": -0.25})
        assert upd.net_sentiment == -0.25


class TestPlaylistViewExposesProvenance:
    def test_source_app_round_trips(self) -> None:
        view = PlaylistView.model_validate(
            {"id": 1, "name": "Peak Hour", "source_app": "rekordbox"}
        )
        assert view.source_app == "rekordbox"

    def test_platform_ids_round_trips(self) -> None:
        view = PlaylistView.model_validate(
            {"id": 1, "name": "Peak Hour", "platform_ids": '{"ym": "12345:67890"}'}
        )
        assert view.platform_ids == '{"ym": "12345:67890"}'

    def test_new_fields_default_none(self) -> None:
        view = PlaylistView.model_validate({"id": 1, "name": "X"})
        assert view.source_app is None
        assert view.platform_ids is None


class TestPlaylistFilterIdRangeAndProvenance:
    @pytest.mark.parametrize("op", ["gt", "gte", "lt", "lte"])
    def test_id_range_lookups(self, op: str) -> None:
        PlaylistFilter.model_validate({f"id__{op}": 100})

    def test_source_of_truth_in(self) -> None:
        PlaylistFilter.model_validate({"source_of_truth__in": ["local", "ym"]})

    def test_parent_id_in(self) -> None:
        PlaylistFilter.model_validate({"parent_id__in": [1, 2, 3]})

    def test_source_app_eq(self) -> None:
        PlaylistFilter.model_validate({"source_app__eq": "rekordbox"})

    def test_source_app_in(self) -> None:
        PlaylistFilter.model_validate({"source_app__in": ["rekordbox", "ym"]})

    def test_source_app_isnull(self) -> None:
        PlaylistFilter.model_validate({"source_app__isnull": True})

    def test_platform_ids_icontains(self) -> None:
        PlaylistFilter.model_validate({"platform_ids__icontains": "ym"})

    def test_platform_ids_isnull(self) -> None:
        PlaylistFilter.model_validate({"platform_ids__isnull": True})


class TestPlaylistCreateUpdateAcceptProvenance:
    def test_create_source_app(self) -> None:
        c = PlaylistCreate.model_validate({"name": "X", "source_app": "rekordbox"})
        assert c.source_app == "rekordbox"

    def test_create_platform_ids(self) -> None:
        c = PlaylistCreate.model_validate({"name": "X", "platform_ids": '{"ym": "1:2"}'})
        assert c.platform_ids == '{"ym": "1:2"}'

    def test_create_source_app_max_length(self) -> None:
        with pytest.raises(ValidationError):
            PlaylistCreate.model_validate({"name": "X", "source_app": "a" * 201})

    def test_update_source_app(self) -> None:
        u = PlaylistUpdate.model_validate({"source_app": "ym"})
        assert u.source_app == "ym"

    def test_update_platform_ids(self) -> None:
        u = PlaylistUpdate.model_validate({"platform_ids": '{"ym": "1:2"}'})
        assert u.platform_ids == '{"ym": "1:2"}'


class TestUnknownLookupsStillRejected:
    def test_track_affinity_typo(self) -> None:
        with pytest.raises(ValidationError):
            TrackAffinityFilter.model_validate({"play_count__contains": 1})

    def test_playlist_typo(self) -> None:
        with pytest.raises(ValidationError):
            PlaylistFilter.model_validate({"name__endswith": "x"})
