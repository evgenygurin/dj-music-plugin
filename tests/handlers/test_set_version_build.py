"""SetVersionBuildHandler tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp.server.context import Context

from app.domain.transition.intent import TransitionIntent
from app.domain.transition.section_context import SectionPairClass
from app.handlers.set_version_build import set_version_build_handler
from app.shared.constants import SectionType
from app.shared.errors import NotFoundError, ValidationError
from app.shared.features import TrackFeatures


@pytest.fixture
def ctx() -> MagicMock:
    c = MagicMock(spec=Context)
    c.info = AsyncMock()
    return c


@pytest.fixture
def session_spy() -> MagicMock:
    s = MagicMock()
    s.flush = AsyncMock()
    return s


@pytest.fixture
def uow(session_spy: MagicMock) -> MagicMock:
    u = MagicMock()
    u.session = session_spy
    u.sets = MagicMock()
    u.sets.get = AsyncMock()
    u.set_versions = MagicMock()
    u.set_versions.create = AsyncMock(return_value=MagicMock(id=10, label="v1", quality_score=0.0))
    u.set_versions.create_items = AsyncMock(return_value=3)
    u.set_versions.get_items = AsyncMock(
        return_value=[
            MagicMock(track_id=1, sort_index=0),
            MagicMock(track_id=2, sort_index=1),
            MagicMock(track_id=3, sort_index=2),
        ]
    )
    u.track_features = MagicMock()
    u.track_features.get_scoring_features_batch = AsyncMock(
        return_value={1: MagicMock(), 2: MagicMock(), 3: MagicMock()}
    )
    u.transitions = MagicMock()
    u.transitions.upsert = AsyncMock(return_value=MagicMock(id=42))
    return u


@pytest.fixture
def scorer() -> MagicMock:
    s = MagicMock()
    score = MagicMock()
    score.overall = 0.8
    score.bpm = score.harmonics = score.energy = 0.8
    score.bass = score.drums = score.vocals = 0.8
    score.hard_reject = False
    score.reject_reason = None
    s.score.return_value = score
    return s


@pytest.mark.asyncio
async def test_builds_version_with_items(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    uow.sets.get.return_value = MagicMock(id=5, name="Test")
    data = {
        "set_id": 5,
        "track_order": [1, 2, 3],
        "label": "v1",
        "generator_run_meta": {"algo": "ga"},
    }

    with patch("app.server.di.get_transition_scorer", AsyncMock(return_value=scorer)):
        result = await set_version_build_handler(ctx, uow, data)

    assert result["version_id"] == 10
    assert result["item_count"] == 3
    assert result["transition_count"] == 2  # N-1 transitions for N tracks
    uow.set_versions.create_items.assert_awaited_once_with(version_id=10, track_order=[1, 2, 3])
    # transitions persisted: N-1 upserts with directed pair fields
    assert uow.transitions.upsert.await_count == 2
    pairs = [
        (c.kwargs["from_track_id"], c.kwargs["to_track_id"])
        for c in uow.transitions.upsert.await_args_list
    ]
    assert pairs == [(1, 2), (2, 3)]


@pytest.mark.asyncio
async def test_unknown_set_raises(ctx: MagicMock, uow: MagicMock, scorer: MagicMock) -> None:
    uow.sets.get.return_value = None
    data = {"set_id": 999, "track_order": [1, 2]}
    with pytest.raises(NotFoundError):
        await set_version_build_handler(ctx, uow, data)


@pytest.mark.asyncio
async def test_empty_track_order_raises_validation(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    uow.sets.get.return_value = MagicMock(id=5)
    data = {"set_id": 5, "track_order": []}
    with pytest.raises(ValidationError):
        await set_version_build_handler(ctx, uow, data)


@pytest.mark.asyncio
async def test_quality_score_averaged(ctx: MagicMock, uow: MagicMock, scorer: MagicMock) -> None:
    uow.sets.get.return_value = MagicMock(id=5, name="S")
    data = {"set_id": 5, "track_order": [1, 2, 3]}

    with patch("app.server.di.get_transition_scorer", AsyncMock(return_value=scorer)):
        result = await set_version_build_handler(ctx, uow, data)

    # 2 transitions, each overall=0.8 → avg 0.8
    assert result["quality_score"] == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_builds_without_scorer_when_lifespan_missing(ctx: MagicMock, uow: MagicMock) -> None:
    uow.sets.get.return_value = MagicMock(id=5, name="S")
    data = {"set_id": 5, "track_order": [1, 2, 3]}

    with patch(
        "app.server.di.get_transition_scorer",
        AsyncMock(side_effect=RuntimeError("TransitionScorer not initialized")),
    ):
        result = await set_version_build_handler(ctx, uow, data)

    assert result["transition_count"] == 0
    assert result["quality_score"] == 0.0


@pytest.mark.asyncio
async def test_persists_hard_rejects_with_reason(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    """In real libraries (e.g. lat'30 mixed-BPM YM-likes set) ~30% of pairs
    hard-reject. The persist path must propagate ``hard_reject=True`` and
    the human-readable ``reject_reason`` to the DB so users can later
    review WHY a transition failed via ``local://sets/{id}/review``.
    """
    uow.sets.get.return_value = MagicMock(id=5, name="S")
    # Make pair (1,2) reject, pair (2,3) succeed.
    good = MagicMock(
        overall=0.8,
        bpm=0.8,
        harmonics=0.8,
        energy=0.8,
        bass=0.8,
        drums=0.8,
        vocals=0.8,
        hard_reject=False,
        reject_reason=None,
    )
    bad = MagicMock(
        overall=0.0,
        bpm=0.0,
        harmonics=0.5,
        energy=0.5,
        bass=0.5,
        drums=0.5,
        vocals=0.5,
        hard_reject=True,
        reject_reason="BPM diff 25.2 > 10.0",
    )
    scorer.score.side_effect = [bad, good]

    data = {"set_id": 5, "track_order": [1, 2, 3]}
    with patch("app.server.di.get_transition_scorer", AsyncMock(return_value=scorer)):
        await set_version_build_handler(ctx, uow, data)

    # Both pairs persisted (hard_reject ones are NOT silently dropped).
    assert uow.transitions.upsert.await_count == 2
    first_call_kwargs = uow.transitions.upsert.await_args_list[0].kwargs
    assert first_call_kwargs["hard_reject"] is True
    assert first_call_kwargs["reject_reason"] == "BPM diff 25.2 > 10.0"
    assert first_call_kwargs["overall_quality"] == 0.0
    second_call_kwargs = uow.transitions.upsert.await_args_list[1].kwargs
    assert second_call_kwargs["hard_reject"] is False
    assert second_call_kwargs["reject_reason"] is None


@pytest.mark.asyncio
async def test_build_persists_same_intent_sections_and_mix_points_it_scores(
    ctx: MagicMock, uow: MagicMock, scorer: MagicMock
) -> None:
    uow.sets.get.return_value = MagicMock(
        id=5,
        name="S",
        template_name="peak_hour_60",
    )
    features = {
        1: TrackFeatures(
            bpm=126.0,
            integrated_lufs=-12.0,
            mix_out_section_id=101,
            mix_out_section_type=int(SectionType.OUTRO),
            mix_out_point_ms=224_000,
        ),
        2: TrackFeatures(
            bpm=128.0,
            integrated_lufs=-10.5,
            mix_in_section_id=202,
            mix_in_section_type=int(SectionType.INTRO),
            mix_in_point_ms=0,
            mix_out_section_id=203,
            mix_out_section_type=int(SectionType.OUTRO),
            mix_out_point_ms=240_000,
        ),
        3: TrackFeatures(
            bpm=129.0,
            integrated_lufs=-10.0,
            mix_in_section_id=304,
            mix_in_section_type=int(SectionType.INTRO),
            mix_in_point_ms=0,
        ),
    }
    uow.track_features.get_scoring_features_batch.return_value = features
    transition_rows = [MagicMock(id=501), MagicMock(id=502)]
    uow.transitions.upsert.side_effect = transition_rows

    with patch("app.server.di.get_transition_scorer", AsyncMock(return_value=scorer)):
        await set_version_build_handler(
            ctx,
            uow,
            {"set_id": 5, "track_order": [1, 2, 3], "label": "aligned"},
        )

    first_score_call = scorer.score.call_args_list[0]
    assert first_score_call.kwargs["intent"] == TransitionIntent.RAMP_UP
    assert (
        first_score_call.kwargs["section_context"].section_pair_class == SectionPairClass.DRUM_ONLY
    )
    first_persist = uow.transitions.upsert.await_args_list[0].kwargs
    assert first_persist["from_section_id"] == 101
    assert first_persist["to_section_id"] == 202
    assert first_persist["overlap_ms"] > 0

    items = await uow.set_versions.get_items(10)
    assert items[0].transition_id == 501
    assert items[0].out_section_id == 101
    assert items[0].mix_out_point_ms == 224_000
    assert items[1].in_section_id == 202
    assert items[1].mix_in_point_ms == 0
