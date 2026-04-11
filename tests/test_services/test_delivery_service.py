"""Tests for DeliveryService — export logging to app_exports table."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.export import AppExport
from app.db.repositories.export import ExportRepository
from app.db.repositories.feature import FeatureRepository
from app.db.repositories.set import SetRepository
from app.db.repositories.track import TrackRepository
from app.db.repositories.transition import TransitionRepository
from app.export.models import ExportTrack, SetExportData
from app.services.delivery_service import DeliveryService


def _make_delivery_service(db: AsyncSession) -> DeliveryService:
    return DeliveryService(
        set_repo=SetRepository(db),
        track_repo=TrackRepository(db),
        feature_repo=FeatureRepository(db),
        transition_repo=TransitionRepository(db),
        export_repo=ExportRepository(db),
    )


# ── BUG 3: app_exports populated after export ──────────


@pytest.mark.asyncio
async def test_log_export_creates_record(db: AsyncSession) -> None:
    """log_export should create an AppExport row in DB."""
    svc = _make_delivery_service(db)

    record = await svc.log_export(
        target_app="dj_music_plugin",
        export_format="m3u8",
        file_path="/tmp/test_set.m3u8",
        file_size=1234,
    )

    assert record is not None
    assert record.id is not None
    assert record.target_app == "dj_music_plugin"
    assert record.export_format == "m3u8"
    assert record.file_path == "/tmp/test_set.m3u8"
    assert record.file_size == 1234


@pytest.mark.asyncio
async def test_log_generated_exports_multiple(db: AsyncSession, tmp_path: Path) -> None:
    """log_generated_exports should create one record per file."""
    svc = _make_delivery_service(db)

    # Create real files to read size from
    m3u8_file = tmp_path / "set.m3u8"
    m3u8_file.write_text("#EXTM3U\ntest")
    json_file = tmp_path / "set.json"
    json_file.write_text('{"set": "test"}')

    logged = await svc.log_generated_exports([str(m3u8_file), str(json_file)])

    assert logged == 2

    result = await db.execute(select(AppExport))
    records = list(result.scalars().all())
    assert len(records) == 2

    formats = {r.export_format for r in records}
    assert "m3u8" in formats
    assert "json_guide" in formats

    for r in records:
        assert r.file_size is not None
        assert r.file_size > 0


@pytest.mark.asyncio
async def test_log_export_without_repo_returns_none(db: AsyncSession) -> None:
    """When export_repo is None, log_export should return None gracefully."""
    svc = DeliveryService(
        set_repo=SetRepository(db),
        track_repo=TrackRepository(db),
        feature_repo=FeatureRepository(db),
        transition_repo=TransitionRepository(db),
        export_repo=None,
    )

    result = await svc.log_export(
        target_app="test", export_format="m3u8", file_path="/tmp/test.m3u8"
    )
    assert result is None


@pytest.mark.asyncio
async def test_generate_exports_logs_to_db(db: AsyncSession, tmp_path: Path) -> None:
    """generate_exports should automatically log files to app_exports."""
    svc = _make_delivery_service(db)
    data = SetExportData(
        name="Test Set",
        tracks=[
            ExportTrack(
                position=0,
                title="Track A",
                artist="Artist 1",
                duration_ms=300000,
                file_path="/music/a.mp3",
                bpm=128.0,
                key_camelot="8A",
                energy_lufs=-8.0,
            ),
        ],
    )

    files = await svc.generate_exports(data, tmp_path, "test_set", ["m3u8", "json"])
    assert len(files) == 2

    result = await db.execute(select(AppExport))
    records = list(result.scalars().all())
    assert len(records) == 2


@pytest.mark.asyncio
async def test_export_single_logs_to_db(db: AsyncSession, tmp_path: Path) -> None:
    """export_single should log the exported file to app_exports."""
    svc = _make_delivery_service(db)
    data = SetExportData(
        name="Single Export",
        tracks=[
            ExportTrack(
                position=0,
                title="Track B",
                artist="Artist 2",
                duration_ms=360000,
                file_path="/music/b.mp3",
            ),
        ],
    )

    out = tmp_path / "test.m3u8"
    result_path = await svc.export_single(data, "m3u8", out)
    assert result_path.exists()

    result = await db.execute(select(AppExport))
    records = list(result.scalars().all())
    assert len(records) == 1
    assert records[0].export_format == "m3u8"


@pytest.mark.asyncio
async def test_build_export_data_ignores_malformed_persisted_recipe_json() -> None:
    """Malformed transition_recipe_json should not break export generation."""
    track_repo = SimpleNamespace(
        get_by_id=AsyncMock(
            side_effect=[
                SimpleNamespace(id=1, title="Track A", duration_ms=300000),
                SimpleNamespace(id=2, title="Track B", duration_ms=300000),
            ]
        ),
        get_artist_names=AsyncMock(return_value="Artist"),
        get_library_file_path=AsyncMock(return_value="/music/test.mp3"),
    )
    feature_repo = SimpleNamespace(
        get_features=AsyncMock(
            side_effect=[
                SimpleNamespace(bpm=128.0, key_code=1, integrated_lufs=-8.0, mood="driving"),
                SimpleNamespace(bpm=130.0, key_code=2, integrated_lufs=-7.0, mood="peak_time"),
            ]
        ),
        get_sections=AsyncMock(return_value=[]),
    )
    transition_repo = SimpleNamespace(
        get_score=AsyncMock(
            return_value=SimpleNamespace(
                overall_quality=0.82,
                transition_type="cut",
                transition_recipe_json="[]",
            )
        )
    )
    svc = DeliveryService(
        set_repo=SimpleNamespace(),
        track_repo=track_repo,
        feature_repo=feature_repo,
        transition_repo=transition_repo,
        export_repo=None,
    )

    data = await svc.build_export_data(
        dj_set=SimpleNamespace(name="Test Set"),
        version=SimpleNamespace(label="v1", quality_score=0.82),
        items=[
            SimpleNamespace(track_id=1, sort_index=0, notes=None),
            SimpleNamespace(track_id=2, sort_index=1, notes=None),
        ],
    )

    assert len(data.transitions) == 1
    transition = data.transitions[0]
    assert transition.transition_type is None
    assert transition.transition_bars is None
    assert transition.djay_transition is None
    assert transition.recipe_steps is None
    assert transition.eq_plan is None
    assert transition.rescue_move is None
