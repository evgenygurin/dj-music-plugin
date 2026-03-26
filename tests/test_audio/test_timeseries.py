"""Tests for TimeseriesStorage — NPZ file save/load/delete."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.audio.timeseries import TimeseriesStorage


@pytest.fixture
def storage(tmp_path: Path) -> TimeseriesStorage:
    """Create a TimeseriesStorage with a temporary base directory."""
    return TimeseriesStorage(base_dir=str(tmp_path / "timeseries"))


@pytest.fixture
def sample_data() -> dict[str, np.ndarray]:
    """Sample frame-level data for testing."""
    rng = np.random.default_rng(42)
    return {
        "frame_energy": rng.random(100).astype(np.float32),
        "frame_centroid": rng.random(100).astype(np.float32),
    }


class TestTimeseriesStorage:
    def test_save_creates_file(
        self, storage: TimeseriesStorage, sample_data: dict[str, np.ndarray]
    ) -> None:
        meta = storage.save(
            track_id=1,
            feature_set_name="energy",
            data=sample_data,
            hop_length=512,
            sample_rate=22050,
        )
        assert Path(meta["storage_uri"]).exists()

    def test_save_returns_correct_metadata(
        self, storage: TimeseriesStorage, sample_data: dict[str, np.ndarray]
    ) -> None:
        meta = storage.save(
            track_id=42,
            feature_set_name="spectral",
            data=sample_data,
            hop_length=512,
            sample_rate=22050,
        )
        assert meta["feature_set_name"] == "spectral"
        assert meta["frame_count"] == 100
        assert meta["hop_length"] == 512
        assert meta["sample_rate"] == 22050
        assert meta["data_type"] == "float32"
        # shape should be valid JSON
        shape = json.loads(meta["shape"])
        assert "frame_energy" in shape
        assert shape["frame_energy"] == [100]

    def test_load_returns_saved_data(
        self, storage: TimeseriesStorage, sample_data: dict[str, np.ndarray]
    ) -> None:
        storage.save(
            track_id=1,
            feature_set_name="energy",
            data=sample_data,
            hop_length=512,
            sample_rate=22050,
        )
        loaded = storage.load(track_id=1, feature_set_name="energy")
        assert loaded is not None
        np.testing.assert_array_almost_equal(loaded["frame_energy"], sample_data["frame_energy"])
        np.testing.assert_array_almost_equal(
            loaded["frame_centroid"], sample_data["frame_centroid"]
        )

    def test_load_nonexistent_returns_none(self, storage: TimeseriesStorage) -> None:
        result = storage.load(track_id=999, feature_set_name="energy")
        assert result is None

    def test_exists_true_after_save(
        self, storage: TimeseriesStorage, sample_data: dict[str, np.ndarray]
    ) -> None:
        assert storage.exists(track_id=1, feature_set_name="energy") is False
        storage.save(
            track_id=1,
            feature_set_name="energy",
            data=sample_data,
            hop_length=512,
            sample_rate=22050,
        )
        assert storage.exists(track_id=1, feature_set_name="energy") is True

    def test_delete_specific_feature_set(
        self, storage: TimeseriesStorage, sample_data: dict[str, np.ndarray]
    ) -> None:
        storage.save(
            track_id=1,
            feature_set_name="energy",
            data=sample_data,
            hop_length=512,
            sample_rate=22050,
        )
        storage.save(
            track_id=1,
            feature_set_name="chroma",
            data=sample_data,
            hop_length=512,
            sample_rate=22050,
        )
        deleted = storage.delete(track_id=1, feature_set_name="energy")
        assert deleted == 1
        assert storage.exists(track_id=1, feature_set_name="energy") is False
        assert storage.exists(track_id=1, feature_set_name="chroma") is True

    def test_delete_all_for_track(
        self, storage: TimeseriesStorage, sample_data: dict[str, np.ndarray]
    ) -> None:
        storage.save(
            track_id=1,
            feature_set_name="energy",
            data=sample_data,
            hop_length=512,
            sample_rate=22050,
        )
        storage.save(
            track_id=1,
            feature_set_name="chroma",
            data=sample_data,
            hop_length=512,
            sample_rate=22050,
        )
        deleted = storage.delete(track_id=1)
        assert deleted == 2
        assert storage.exists(track_id=1, feature_set_name="energy") is False
        assert storage.exists(track_id=1, feature_set_name="chroma") is False

    def test_delete_nonexistent_returns_zero(self, storage: TimeseriesStorage) -> None:
        deleted = storage.delete(track_id=999)
        assert deleted == 0

    def test_list_feature_sets(
        self, storage: TimeseriesStorage, sample_data: dict[str, np.ndarray]
    ) -> None:
        storage.save(
            track_id=1,
            feature_set_name="energy",
            data=sample_data,
            hop_length=512,
            sample_rate=22050,
        )
        storage.save(
            track_id=1,
            feature_set_name="chroma",
            data=sample_data,
            hop_length=512,
            sample_rate=22050,
        )
        storage.save(
            track_id=1,
            feature_set_name="spectral",
            data=sample_data,
            hop_length=512,
            sample_rate=22050,
        )
        feature_sets = storage.list_feature_sets(track_id=1)
        assert sorted(feature_sets) == ["chroma", "energy", "spectral"]

    def test_list_feature_sets_empty(self, storage: TimeseriesStorage) -> None:
        assert storage.list_feature_sets(track_id=999) == []

    def test_multiple_tracks_isolated(
        self, storage: TimeseriesStorage, sample_data: dict[str, np.ndarray]
    ) -> None:
        """Different tracks should have isolated storage."""
        data_2 = {"frame_energy": np.ones(50, dtype=np.float32)}
        storage.save(
            track_id=1,
            feature_set_name="energy",
            data=sample_data,
            hop_length=512,
            sample_rate=22050,
        )
        storage.save(
            track_id=2, feature_set_name="energy", data=data_2, hop_length=512, sample_rate=22050
        )

        loaded_1 = storage.load(track_id=1, feature_set_name="energy")
        loaded_2 = storage.load(track_id=2, feature_set_name="energy")
        assert loaded_1 is not None
        assert loaded_2 is not None
        assert loaded_1["frame_energy"].shape != loaded_2["frame_energy"].shape

    def test_save_2d_data(self, storage: TimeseriesStorage) -> None:
        """Should handle 2D arrays (e.g., chroma: 12 bins x N frames)."""
        rng = np.random.default_rng(42)
        data_2d = {"chroma": rng.random((100, 12)).astype(np.float32)}
        meta = storage.save(
            track_id=1,
            feature_set_name="chroma",
            data=data_2d,
            hop_length=512,
            sample_rate=22050,
        )
        assert meta["frame_count"] == 100
        shape = json.loads(meta["shape"])
        assert shape["chroma"] == [100, 12]

        loaded = storage.load(track_id=1, feature_set_name="chroma")
        assert loaded is not None
        np.testing.assert_array_almost_equal(loaded["chroma"], data_2d["chroma"])
