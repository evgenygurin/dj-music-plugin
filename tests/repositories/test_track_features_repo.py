"""TrackFeaturesRepository domain methods."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base, Track, TrackAudioFeaturesComputed
from app.repositories.track_features import (
    TrackFeaturesRepository,
    _serialize_vectors,
)


@pytest_asyncio.fixture
async def repo(engine: AsyncEngine, session: AsyncSession) -> TrackFeaturesRepository:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return TrackFeaturesRepository(session)


@pytest.mark.asyncio
async def test_get_scoring_features_batch(
    repo: TrackFeaturesRepository, session: AsyncSession
) -> None:
    t1, t2, t3 = Track(title="a"), Track(title="b"), Track(title="c")
    session.add_all([t1, t2, t3])
    await session.flush()
    session.add_all(
        [
            TrackAudioFeaturesComputed(track_id=t1.id, bpm=128.0, analysis_level=3),
            TrackAudioFeaturesComputed(track_id=t2.id, bpm=130.0, analysis_level=3),
        ]
    )
    await session.flush()
    result = await repo.get_scoring_features_batch([t1.id, t2.id, t3.id])
    assert set(result.keys()) == {t1.id, t2.id}
    assert result[t1.id].bpm == 128.0


@pytest.mark.asyncio
async def test_set_mood(repo: TrackFeaturesRepository, session: AsyncSession) -> None:
    t = Track(title="a")
    session.add(t)
    await session.flush()
    session.add(TrackAudioFeaturesComputed(track_id=t.id, bpm=128.0))
    await session.flush()
    await repo.set_mood(t.id, mood="peak_time", confidence=0.82)
    row = await session.get(TrackAudioFeaturesComputed, t.id)
    assert row is not None
    assert row.mood == "peak_time"
    assert row.mood_confidence == 0.82


def test_serialize_vectors_encodes_lists_to_json_strings() -> None:
    """Pipeline returns vectors as ``list[float]`` but the columns are
    ``Mapped[str | None]`` over ``String(...)`` — the helper must encode
    them to JSON strings or asyncpg raises ``DataError``.
    """
    raw = {
        "bpm": 128.0,
        "mfcc_vector": [0.1, 0.2, 0.3],
        "tonnetz_vector": [0.4, -0.1, 0.0, 0.2, -0.3, 0.1],
        "tempogram_ratio_vector": [1.0, 0.5, 0.0],
        "beat_loudness_band_ratio": [0.6, 0.1, 0.2, 0.05, 0.025, 0.025],
        "phrase_boundaries_ms": [0, 32000, 64000],
        "mood": "peak_time",
        "atonality": False,
    }
    out = _serialize_vectors(raw)
    # Scalars / strings / bools pass through untouched.
    assert out["bpm"] == 128.0
    assert out["mood"] == "peak_time"
    assert out["atonality"] is False
    # Vector columns are now JSON strings round-trippable to the original.
    for col in (
        "mfcc_vector",
        "tonnetz_vector",
        "tempogram_ratio_vector",
        "beat_loudness_band_ratio",
        "phrase_boundaries_ms",
    ):
        assert isinstance(out[col], str), f"{col} must be str"
        assert json.loads(out[col]) == raw[col]


def test_serialize_vectors_passes_already_encoded_strings_through() -> None:
    """If a caller has already JSON-encoded a vector, leave it alone."""
    pre_encoded = json.dumps([0.1, 0.2])
    out = _serialize_vectors({"mfcc_vector": pre_encoded})
    assert out["mfcc_vector"] == pre_encoded


def test_serialize_vectors_handles_none_and_missing() -> None:
    """``None`` is preserved; missing columns are not invented."""
    out = _serialize_vectors({"mfcc_vector": None, "bpm": 130.0})
    assert out["mfcc_vector"] is None
    assert out["bpm"] == 130.0
    assert "tonnetz_vector" not in out


def test_serialize_vectors_handles_numpy_ndarray() -> None:
    """Pipeline analyzers historically return ``np.ndarray`` from some
    paths; ``json.dumps`` cannot encode ndarray directly. The helper
    must coerce via ``.tolist()`` so a future analyzer that forgets the
    explicit conversion doesn't crash the L3 sweep.
    """
    import numpy as np

    arr = np.array([0.1, 0.2, 0.3], dtype=np.float64)
    out = _serialize_vectors({"mfcc_vector": arr})
    assert isinstance(out["mfcc_vector"], str)
    assert json.loads(out["mfcc_vector"]) == [0.1, 0.2, 0.3]


def test_serialize_vectors_handles_tuple() -> None:
    """Tuples are valid JSON arrays once converted to list."""
    out = _serialize_vectors({"tonnetz_vector": (0.1, 0.2, 0.3)})
    assert json.loads(out["tonnetz_vector"]) == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_upsert_serializes_vector_columns(
    repo: TrackFeaturesRepository, session: AsyncSession
) -> None:
    """Regression for asyncpg ``DataError: expected str, got list`` on
    ``track_audio_features_computed`` insert when handler splat
    ``**result.features`` (vectors arrive as lists)."""
    t = Track(title="vector-test")
    session.add(t)
    await session.flush()

    await repo.upsert(
        track_id=t.id,
        analysis_level=3,
        bpm=128.0,
        mfcc_vector=[0.1, 0.2, 0.3],
        tonnetz_vector=[0.4, -0.1, 0.0, 0.2, -0.3, 0.1],
        tempogram_ratio_vector=[1.0, 0.5, 0.0],
        beat_loudness_band_ratio=[0.6, 0.1, 0.2, 0.05, 0.025, 0.025],
        phrase_boundaries_ms=[0, 32000, 64000],
    )

    row = await session.get(TrackAudioFeaturesComputed, t.id)
    assert row is not None
    # Stored as JSON-encoded strings; assert round-trip parses cleanly.
    assert json.loads(row.mfcc_vector or "null") == [0.1, 0.2, 0.3]
    assert json.loads(row.tonnetz_vector or "null") == [0.4, -0.1, 0.0, 0.2, -0.3, 0.1]
    assert json.loads(row.phrase_boundaries_ms or "null") == [0, 32000, 64000]
