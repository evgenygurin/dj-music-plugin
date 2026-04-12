"""Tests for section-context wiring in SetScoringService."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from dj_music.core.constants import SectionType
from dj_music.schemas.audio import TrackFeatures
from dj_music.services.set.scoring import SetScoringService
from dj_music.transition.score import TransitionScore
from dj_music.transition.scorer import TransitionScorer


def _track() -> TrackFeatures:
    return TrackFeatures(
        bpm=132.0,
        key_code=14,
        integrated_lufs=-8.0,
        spectral_centroid_hz=2500.0,
        energy_mean=0.5,
        onset_rate=4.0,
        kick_prominence=0.5,
    )


class _FakeSetRepo:
    def __init__(self, items: list[SimpleNamespace]) -> None:
        self._items = items

    async def load_version_with_items(
        self, set_id: int
    ) -> tuple[SimpleNamespace, list[SimpleNamespace]]:
        return SimpleNamespace(id=99), self._items


class _FakeFeatureRepo:
    def __init__(
        self,
        features_by_track: dict[int, TrackFeatures],
        sections_by_track: dict[int, list[SimpleNamespace]] | None = None,
    ) -> None:
        self._features = features_by_track
        self._sections = sections_by_track or {}

    async def get_scoring_features(self, track_id: int) -> TrackFeatures | None:
        return self._features.get(track_id)

    async def get_sections(self, track_id: int) -> list[SimpleNamespace]:
        return self._sections.get(track_id, [])

    async def get_all_track_ids_with_features(self) -> list[int]:
        return list(self._features.keys())

    async def get_scoring_features_batch(self, track_ids: list[int]) -> dict[int, TrackFeatures]:
        return {
            track_id: features
            for track_id, features in self._features.items()
            if track_id in track_ids
        }


class _FakeTransitionRepo:
    def __init__(self) -> None:
        self.rows: dict[tuple[int, int], object] = {}

    async def get_score(self, from_id: int, to_id: int):
        return self.rows.get((from_id, to_id))

    async def get_scores_batch(
        self,
        pairs: list[tuple[int, int]],
    ) -> dict[tuple[int, int], object]:
        return {pair: self.rows[pair] for pair in pairs if pair in self.rows}

    async def save_score(self, transition):
        self.rows[(transition.from_track_id, transition.to_track_id)] = transition
        return transition


@pytest.mark.asyncio
async def test_score_set_transitions_uses_explicit_section_ids(monkeypatch) -> None:
    captured_contexts = []

    def _fake_score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        intent=None,
        section_context=None,
    ) -> TransitionScore:
        captured_contexts.append(section_context)
        return TransitionScore(
            bpm=0.8,
            harmonic=0.8,
            energy=0.8,
            spectral=0.8,
            groove=0.8,
            timbral=0.8,
            overall=0.8,
        )

    monkeypatch.setattr(TransitionScorer, "score", _fake_score)

    items = [
        SimpleNamespace(
            track_id=1,
            sort_index=0,
            out_section_id=int(SectionType.OUTRO),
            in_section_id=None,
            mix_in_point_ms=None,
            mix_out_point_ms=None,
        ),
        SimpleNamespace(
            track_id=2,
            sort_index=1,
            out_section_id=None,
            in_section_id=int(SectionType.INTRO),
            mix_in_point_ms=None,
            mix_out_point_ms=None,
        ),
    ]
    svc = SetScoringService(
        set_repo=_FakeSetRepo(items),  # type: ignore[arg-type]
        feature_repo=_FakeFeatureRepo({1: _track(), 2: _track()}),  # type: ignore[arg-type]
        transition_repo=_FakeTransitionRepo(),  # type: ignore[arg-type]
    )

    result = await svc.score_set_transitions(set_id=1)

    assert len(captured_contexts) == 1
    assert captured_contexts[0] is not None
    assert captured_contexts[0].is_drum_only_pair is True
    assert result["transitions"][0]["used_section_context"] is True
    assert result["transitions"][0]["from_section_id"] == int(SectionType.OUTRO)
    assert result["transitions"][0]["to_section_id"] == int(SectionType.INTRO)


@pytest.mark.asyncio
async def test_score_set_transitions_falls_back_to_mix_points(monkeypatch) -> None:
    captured_contexts = []

    def _fake_score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        intent=None,
        section_context=None,
    ) -> TransitionScore:
        captured_contexts.append(section_context)
        return TransitionScore(
            bpm=0.75,
            harmonic=0.75,
            energy=0.75,
            spectral=0.75,
            groove=0.75,
            timbral=0.75,
            overall=0.75,
        )

    monkeypatch.setattr(TransitionScorer, "score", _fake_score)

    items = [
        SimpleNamespace(
            track_id=10,
            sort_index=0,
            out_section_id=None,
            in_section_id=None,
            mix_in_point_ms=None,
            mix_out_point_ms=210_000,
        ),
        SimpleNamespace(
            track_id=11,
            sort_index=1,
            out_section_id=None,
            in_section_id=None,
            mix_in_point_ms=2_000,
            mix_out_point_ms=None,
        ),
    ]
    sections = {
        10: [
            SimpleNamespace(section_type=int(SectionType.OUTRO), start_ms=200_000, end_ms=240_000)
        ],
        11: [SimpleNamespace(section_type=int(SectionType.INTRO), start_ms=0, end_ms=30_000)],
    }
    svc = SetScoringService(
        set_repo=_FakeSetRepo(items),  # type: ignore[arg-type]
        feature_repo=_FakeFeatureRepo({10: _track(), 11: _track()}, sections),  # type: ignore[arg-type]
        transition_repo=_FakeTransitionRepo(),  # type: ignore[arg-type]
    )

    result = await svc.score_set_transitions(set_id=1)

    assert len(captured_contexts) == 1
    assert captured_contexts[0] is not None
    assert captured_contexts[0].from_section == SectionType.OUTRO
    assert captured_contexts[0].to_section == SectionType.INTRO
    assert result["transitions"][0]["used_section_context"] is True
    assert result["transitions"][0]["from_section_id"] == int(SectionType.OUTRO)
    assert result["transitions"][0]["to_section_id"] == int(SectionType.INTRO)


@pytest.mark.asyncio
async def test_score_set_transitions_keeps_fallback_without_context(monkeypatch) -> None:
    captured_contexts = []

    def _fake_score(
        self,
        from_t: TrackFeatures,
        to_t: TrackFeatures,
        *,
        intent=None,
        section_context=None,
    ) -> TransitionScore:
        captured_contexts.append(section_context)
        return TransitionScore(
            bpm=0.7,
            harmonic=0.7,
            energy=0.7,
            spectral=0.7,
            groove=0.7,
            timbral=0.7,
            overall=0.7,
        )

    monkeypatch.setattr(TransitionScorer, "score", _fake_score)

    items = [
        SimpleNamespace(
            track_id=21,
            sort_index=0,
            out_section_id=None,
            in_section_id=None,
            mix_in_point_ms=None,
            mix_out_point_ms=None,
        ),
        SimpleNamespace(
            track_id=22,
            sort_index=1,
            out_section_id=None,
            in_section_id=None,
            mix_in_point_ms=None,
            mix_out_point_ms=None,
        ),
    ]
    svc = SetScoringService(
        set_repo=_FakeSetRepo(items),  # type: ignore[arg-type]
        feature_repo=_FakeFeatureRepo({21: _track(), 22: _track()}),  # type: ignore[arg-type]
        transition_repo=_FakeTransitionRepo(),  # type: ignore[arg-type]
    )

    result = await svc.score_set_transitions(set_id=1)

    assert len(captured_contexts) == 1
    assert captured_contexts[0] is None
    assert result["transitions"][0]["used_section_context"] is False
    assert result["transitions"][0]["from_section_id"] is None
    assert result["transitions"][0]["to_section_id"] is None


@pytest.mark.asyncio
async def test_get_transition_candidates_scores_full_library() -> None:
    current = _track()
    close_match = _track()
    close_match.bpm = 133.0
    close_match.key_code = 14
    close_match.integrated_lufs = -8.5
    close_match.mood = "driving"

    decent_match = _track()
    decent_match.bpm = 130.0
    decent_match.key_code = 12
    decent_match.integrated_lufs = -9.0
    decent_match.mood = "hypnotic"

    hard_reject = _track()
    hard_reject.bpm = 148.0
    hard_reject.key_code = 14
    hard_reject.integrated_lufs = -8.0

    svc = SetScoringService(
        set_repo=_FakeSetRepo([]),  # type: ignore[arg-type]
        feature_repo=_FakeFeatureRepo(  # type: ignore[arg-type]
            {
                10: current,
                11: close_match,
                12: decent_match,
                13: hard_reject,
            }
        ),
        transition_repo=_FakeTransitionRepo(),  # type: ignore[arg-type]
    )

    result = await svc.get_transition_candidates(track_id=10, top_n=5)

    assert result["track_id"] == 10
    assert result["pool_size"] == 3
    assert result["scored"] == 2
    assert [candidate["to_track_id"] for candidate in result["candidates"]] == [11, 12]
    assert result["candidates"][0]["overall_quality"] >= result["candidates"][1]["overall_quality"]
    assert result["candidates"][0]["bpm_distance"] == pytest.approx(1.0, abs=0.01)
    assert result["candidates"][0]["camelot"] == "8A"
    assert result["candidates"][1]["key_distance"] == 1


@pytest.mark.asyncio
async def test_get_transition_candidates_requires_features() -> None:
    svc = SetScoringService(
        set_repo=_FakeSetRepo([]),  # type: ignore[arg-type]
        feature_repo=_FakeFeatureRepo({}),  # type: ignore[arg-type]
        transition_repo=_FakeTransitionRepo(),  # type: ignore[arg-type]
    )

    result = await svc.get_transition_candidates(track_id=404, top_n=5)

    assert result["track_id"] == 404
    assert result["candidates"] == []
    assert result["scored"] == 0
    assert "analyze first" in result["note"].lower()
