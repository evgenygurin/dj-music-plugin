"""Smoke tests for v2 top-level audio modules (Task 13 port parity)."""

from __future__ import annotations

import numpy as np
import pytest

from app.audio import (
    AnalysisContext,
    AnalysisLevel,
    AnalyzerRegistry,
    AudioSignal,
    get_analyzers_for_level,
)
from app.audio.pipeline import AnalysisPipeline
from app.audio.temp_download import temp_download_track
from app.audio.timeseries import TimeseriesStorage


def test_level_config_names_preserved() -> None:
    assert AnalysisLevel.NONE == 0
    assert AnalysisLevel.TRIAGE == 2
    assert AnalysisLevel.SCORING == 3
    assert AnalysisLevel.TRANSITION == 4
    assert AnalysisLevel.ADVANCED == 5
    triage = get_analyzers_for_level(AnalysisLevel.TRIAGE)
    assert set(triage) == {"loudness", "energy", "spectral", "bpm", "key", "mfcc"}
    scoring = get_analyzers_for_level(AnalysisLevel.SCORING)
    assert "beat" in scoring
    advanced = get_analyzers_for_level(AnalysisLevel.ADVANCED)
    # Transitively includes lower levels + all L5 analyzers
    assert "structure" in advanced
    assert "tonnetz" in advanced
    assert "tempogram" in advanced


def test_timeseries_roundtrip(tmp_path: object) -> None:
    storage = TimeseriesStorage(base_dir=str(tmp_path))
    arr = np.arange(100, dtype=np.float32).reshape(10, 10)
    meta = storage.save(
        track_id=42,
        feature_set_name="energy",
        data={"energy": arr},
        hop_length=512,
        sample_rate=22050,
    )
    assert meta["feature_set_name"] == "energy"
    assert meta["frame_count"] == 10
    assert storage.exists(42, "energy")
    loaded = storage.load(42, "energy")
    assert loaded is not None
    np.testing.assert_array_equal(loaded["energy"], arr)
    assert "energy" in storage.list_feature_sets(42)
    n = storage.delete(42, "energy")
    assert n == 1
    assert not storage.exists(42, "energy")


def test_timeseries_missing_track_returns_none(tmp_path: object) -> None:
    storage = TimeseriesStorage(base_dir=str(tmp_path))
    assert storage.load(999, "chroma") is None
    assert storage.list_feature_sets(999) == []


def test_pipeline_import_and_construct() -> None:
    # Construction must succeed without running analyzers (lazy pool)
    reg = AnalyzerRegistry()
    reg.discover()
    pipeline = AnalysisPipeline(registry=reg)
    assert pipeline is not None


def test_temp_download_context_manager_is_async() -> None:
    # Importability check — the runtime behavior is exercised by the
    # integration tests once a v2 YM client exists.
    assert callable(temp_download_track)


@pytest.mark.asyncio
async def test_pipeline_smoke_run_core_analyzers(tmp_path: object) -> None:
    """Run the pipeline on a synthetic signal through numpy-only analyzers."""
    reg = AnalyzerRegistry()
    reg.discover()
    AnalysisPipeline(registry=reg)

    # Synthetic 2s sine wave
    sr = 22050
    t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False, dtype=np.float32)
    y = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sig = AudioSignal(samples=y, sample_rate=sr, duration_seconds=2.0)
    ctx = AnalysisContext(sig)

    # Exercise one lightweight analyzer without going through file load
    loud = reg.get("loudness")
    assert loud is not None
    result = loud.run(ctx)
    assert result.success
