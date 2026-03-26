"""Tests for DeliveryService — export logging to app_exports table."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.export import AppExport
from app.repositories.export import ExportRepository
from app.repositories.feature import FeatureRepository
from app.repositories.set import SetRepository
from app.repositories.track import TrackRepository
from app.repositories.transition import TransitionRepository
from app.services.delivery_service import DeliveryService
from app.services.export import ExportTrack, SetExportData


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
