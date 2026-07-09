from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.repositories.stem_features import StemFeaturesRepository
from app.repositories.track_embedding import TrackEmbeddingRepository
from app.repositories.cross_similarity import CrossSimilarityRepository
from app.repositories.feature_extraction import FeatureExtractionRunRepository


@pytest.mark.asyncio
async def test_stem_features_upsert() -> None:
    session = AsyncMock()
    repo = StemFeaturesRepository(session)
    features = {"bpm": 130.0, "integrated_lufs": -8.5}

    await repo.upsert(track_id=1, stem_name="drums", features=features)

    session.merge.assert_called_once()


@pytest.mark.asyncio
async def test_track_embedding_search_similar() -> None:
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.fetchall.return_value = [
        MagicMock(id=2, similarity=0.85),
        MagicMock(id=3, similarity=0.72),
    ]
    session.execute = AsyncMock(return_value=result_mock)
    repo = TrackEmbeddingRepository(session)
    query = np.zeros(256, dtype=np.float32)

    results = await repo.search_similar(query, embedding_type="full", limit=5)

    assert len(results) == 2
    assert results[0] == (2, 0.85)
    assert results[1] == (3, 0.72)
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_cross_similarity_upsert() -> None:
    session = AsyncMock()
    repo = CrossSimilarityRepository(session)

    await repo.upsert(
        track_a_id=1, track_b_id=2, stem_name="original",
        data={"best_match_offset_ms": 500.0, "best_match_score": 0.87},
    )

    session.merge.assert_called_once()


@pytest.mark.asyncio
async def test_feature_extraction_create_and_update() -> None:
    session = AsyncMock()
    session.add = MagicMock()
    repo = FeatureExtractionRunRepository(session)

    run = await repo.create(track_id=1, pipeline_name="l6_deep_analysis", pipeline_version="1.0.0")

    session.add.assert_called_once()
    assert run.track_id == 1

    await repo.update(1, status="completed")
    session.execute.assert_called()
