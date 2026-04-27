"""Audit iteration 1: ``ui_library_dashboard`` + ``ui_camelot_wheel``
silently capped at 10000 rows / track ids.

Live probe on a 24k-track library returned ``mood_distribution`` summing
to ~9.9k and ``camelot_distribution`` summing to exactly 10000 because
both gather paths hardcoded ``LIMIT 10000`` from the pre-scale era. With
the production library at 24k+ tracks, ~60% of the data was silently
dropped from the dashboard.

This module pins:

* ``_gather`` aggregates every analyzed row, no in-memory cap.
* ``bpm_histogram`` is emitted in ascending bucket order, not Counter
  insertion order. Live output had buckets like ``120-124, 125-129,
  135-139, 130-134`` — out of order, which broke chart rendering on
  Prefab-blind clients that consume the JSON fallback directly.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Base, Track, TrackAudioFeaturesComputed
from app.tools.ui import camelot_wheel as cw_mod
from app.tools.ui import library_dashboard as ld_mod


class _Uow:
    """Minimal UoW shim — every UI gather function accesses the same
    handful of methods (tracks.count, tracks.filter, track_features.count,
    track_features.session)."""

    def __init__(self, session: AsyncSession) -> None:
        from app.repositories.track import TrackRepository
        from app.repositories.track_features import TrackFeaturesRepository

        self.tracks = TrackRepository(session)
        self.track_features = TrackFeaturesRepository(session)


@pytest_asyncio.fixture
async def seeded_uow(engine: AsyncEngine, session: AsyncSession) -> _Uow:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 12 rows is enough — the test asserts NO cap, not the magic number.
    bpm_choices = [122.0, 124.5, 128.0, 132.0, 137.0, 145.0, 152.0]
    for i in range(12):
        t = Track(title=f"Track {i}")
        session.add(t)
        await session.flush()
        session.add(
            TrackAudioFeaturesComputed(
                track_id=t.id,
                bpm=bpm_choices[i % len(bpm_choices)],
                key_code=i % 24,
                mood="acid" if i % 2 == 0 else "industrial",
            )
        )
    await session.flush()
    return _Uow(session)


@pytest.mark.asyncio
async def test_dashboard_includes_every_analyzed_row(seeded_uow: _Uow) -> None:
    data = await ld_mod._gather(seeded_uow)  # type: ignore[arg-type]
    mood_total = sum(data["mood_distribution"].values())
    camelot_total = sum(data["camelot_distribution"].values())
    bpm_total = sum(data["bpm_histogram"].values())
    assert mood_total == 12, f"mood_distribution dropped rows: {mood_total}/12"
    assert camelot_total == 12, f"camelot_distribution dropped rows: {camelot_total}/12"
    assert bpm_total == 12, f"bpm_histogram dropped rows: {bpm_total}/12"


@pytest.mark.asyncio
async def test_dashboard_bpm_histogram_buckets_in_ascending_order(
    seeded_uow: _Uow,
) -> None:
    data = await ld_mod._gather(seeded_uow)  # type: ignore[arg-type]
    expected_order = [label for label, _, _ in ld_mod._BPM_BUCKETS]
    actual_order = list(data["bpm_histogram"].keys())
    assert actual_order == expected_order, (
        f"bpm_histogram bucket order mismatch:\n"
        f"  expected: {expected_order}\n"
        f"  actual:   {actual_order}"
    )


@pytest.mark.asyncio
async def test_camelot_wheel_total_tracks_matches_full_library(
    seeded_uow: _Uow,
) -> None:
    data = await cw_mod._gather(seeded_uow, playlist_id=None)  # type: ignore[arg-type]
    assert data["total_tracks"] == 12, (
        f"ui_camelot_wheel.total_tracks dropped rows: {data['total_tracks']}/12 "
        "(library cap regression — should equal entire library)"
    )
