from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_deep_analyze_track_delegates_to_handler() -> None:
    from app.tools.deep_analysis import deep_analyze_track

    uow = MagicMock()
    with patch(
        "app.tools.deep_analysis.handle_deep_analyze_track",
        new_callable=AsyncMock,
        return_value={"track_id": 1, "job_id": 42, "status": "pending"},
    ) as mock_handler:
        result = await deep_analyze_track(track_id=1, uow=uow)

    mock_handler.assert_called_once_with(1, uow)
    assert result["job_id"] == 42


@pytest.mark.asyncio
async def test_deep_analyze_pool_delegates_to_handler() -> None:
    from app.tools.deep_analysis import deep_analyze_pool

    uow = MagicMock()
    with patch(
        "app.tools.deep_analysis.handle_deep_analyze_track",
        new_callable=AsyncMock,
        side_effect=[
            {"track_id": 1, "job_id": 42, "status": "pending"},
            {"track_id": 2, "job_id": 43, "status": "pending"},
        ],
    ) as mock_handler:
        result = await deep_analyze_pool(track_ids=[1, 2], uow=uow)

    assert mock_handler.call_count == 2
    assert result["total"] == 2
    assert result["results"]["1"]["job_id"] == 42
    assert result["results"]["2"]["job_id"] == 43


@pytest.mark.asyncio
async def test_find_compatible_tracks_delegates_to_repo() -> None:
    from app.tools.deep_analysis import find_compatible_tracks

    uow = MagicMock()
    emb = MagicMock()
    emb.embedding = [0.1] * 256
    uow.track_embeddings = MagicMock()
    uow.track_embeddings.get_for_type = AsyncMock(return_value=emb)
    uow.track_embeddings.search_similar = AsyncMock(return_value=[(2, 0.95), (3, 0.87)])

    result = await find_compatible_tracks(active_track_ids=[1], uow=uow)

    assert len(result) == 2
    assert result[0]["track_id"] == 2
    assert result[0]["similarity"] == 0.95
    assert result[1]["track_id"] == 3
    assert result[1]["similarity"] == 0.87


@pytest.mark.asyncio
async def test_get_cross_similarity_returns_scores() -> None:
    from app.tools.deep_analysis import get_cross_similarity

    uow = MagicMock()
    uow.cross_similarity = MagicMock()
    uow.cross_similarity.get_for_pair = AsyncMock(
        return_value=MagicMock(
            track_a_id=1,
            track_b_id=2,
            best_match_offset_ms=100.0,
            best_match_score=0.85,
            alignment_path={"path": [[0, 0], [1, 1]]},
            segment_matches={"segments": []},
        )
    )

    result = await get_cross_similarity(track_a_id=1, track_b_id=2, uow=uow)

    assert result is not None
    assert result["track_a_id"] == 1
    assert result["track_b_id"] == 2
    assert result["best_match_score"] == 0.85


@pytest.mark.asyncio
async def test_get_cross_similarity_returns_none_when_missing() -> None:
    from app.tools.deep_analysis import get_cross_similarity

    uow = MagicMock()
    uow.cross_similarity = MagicMock()
    uow.cross_similarity.get_for_pair = AsyncMock(return_value=None)

    result = await get_cross_similarity(track_a_id=1, track_b_id=2, uow=uow)

    assert result is None
