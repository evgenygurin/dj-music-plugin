"""Timeseries storage — save/load frame-level audio features as NPZ files.

Frame-level data (energy, chroma, spectral features per frame) is too large
for the DB, so it's stored on disk as compressed NPZ files.

Directory layout:
    {cache_dir}/timeseries/{track_id}/
        energy.npz
        chroma.npz
        spectral.npz
        beats.npz

The DB table ``timeseries_references`` stores metadata pointers:
    feature_set_name, storage_uri, frame_count, hop_length, sample_rate, data_type, shape.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from app.config import get_settings


class TimeseriesStorage:
    """Save and load frame-level feature data as NPZ files on disk."""

    def __init__(self, base_dir: str | None = None) -> None:
        if base_dir:
            self._base_dir = Path(base_dir)
        else:
            self._base_dir = Path(get_settings().audio.cache_dir) / "timeseries"

    def _track_dir(self, track_id: int) -> Path:
        """Get the directory for a track's timeseries data."""
        return self._base_dir / str(track_id)

    def save(
        self,
        track_id: int,
        feature_set_name: str,
        data: dict[str, np.ndarray],
        hop_length: int,
        sample_rate: int,
    ) -> dict[str, Any]:
        """Save frame-level data as an NPZ file.

        Args:
            track_id: The track to associate data with.
            feature_set_name: Name of the feature set (e.g., "energy", "chroma").
            data: Dict of array name -> numpy array to save.
            hop_length: Hop length used to compute frames.
            sample_rate: Sample rate of the source audio.

        Returns:
            Metadata dict suitable for creating a ``TimeseriesReference`` record:
            {feature_set_name, storage_uri, frame_count, hop_length, sample_rate,
             data_type, shape}.
        """
        track_dir = self._track_dir(track_id)
        track_dir.mkdir(parents=True, exist_ok=True)

        file_path = track_dir / f"{feature_set_name}.npz"
        np.savez_compressed(str(file_path), **data)  # type: ignore[arg-type]

        # Determine frame_count and shape from the first array
        first_key = next(iter(data))
        first_array = data[first_key]
        frame_count = first_array.shape[0] if first_array.ndim >= 1 else 1
        shape_desc = json.dumps({k: list(v.shape) for k, v in data.items()})

        return {
            "feature_set_name": feature_set_name,
            "storage_uri": str(file_path),
            "frame_count": frame_count,
            "hop_length": hop_length,
            "sample_rate": sample_rate,
            "data_type": str(first_array.dtype),
            "shape": shape_desc,
        }

    def load(
        self,
        track_id: int,
        feature_set_name: str,
    ) -> dict[str, np.ndarray] | None:
        """Load frame-level data from an NPZ file.

        Returns:
            Dict of array name -> numpy array, or None if file doesn't exist.
        """
        file_path = self._track_dir(track_id) / f"{feature_set_name}.npz"
        if not file_path.exists():
            return None

        npz = np.load(str(file_path))
        return dict(npz)

    def exists(self, track_id: int, feature_set_name: str) -> bool:
        """Check if timeseries data exists for a track + feature set."""
        file_path = self._track_dir(track_id) / f"{feature_set_name}.npz"
        return file_path.exists()

    def delete(self, track_id: int, feature_set_name: str | None = None) -> int:
        """Delete timeseries data for a track.

        Args:
            track_id: The track whose data to delete.
            feature_set_name: If provided, delete only this feature set.
                If None, delete all timeseries data for the track.

        Returns:
            Number of files deleted.
        """
        track_dir = self._track_dir(track_id)
        if not track_dir.exists():
            return 0

        deleted = 0
        if feature_set_name:
            file_path = track_dir / f"{feature_set_name}.npz"
            if file_path.exists():
                file_path.unlink()
                deleted = 1
        else:
            for npz_file in track_dir.glob("*.npz"):
                npz_file.unlink()
                deleted += 1
            # Remove empty directory
            if not any(track_dir.iterdir()):
                track_dir.rmdir()

        return deleted

    def list_feature_sets(self, track_id: int) -> list[str]:
        """List available feature sets for a track."""
        track_dir = self._track_dir(track_id)
        if not track_dir.exists():
            return []
        return [f.stem for f in sorted(track_dir.glob("*.npz"))]
