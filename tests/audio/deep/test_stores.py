from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.audio.deep.timeseries_store import upload_timeseries
from app.audio.deep.waveform_store import build_waveform


@pytest.mark.asyncio
async def test_upload_timeseries_calls_storage() -> None:
    storage = MagicMock()
    storage.upload = AsyncMock()

    await upload_timeseries(storage, track_id=1, stem_name="original", data={"energy": np.array([0.1, 0.2])})

    storage.upload.assert_called()


def test_build_waveform_returns_1000_points(tmp_path: Path) -> None:
    import soundfile as sf
    sr = 44100
    sig = np.random.default_rng(42).random(sr * 5).astype(np.float32) * 0.3
    ap = tmp_path / "test.wav"
    sf.write(str(ap), sig, sr)

    peaks = build_waveform(ap, n_points=1000)
    assert len(peaks) == 1000
    assert all(0.0 <= p <= 1.0 for p in peaks)
