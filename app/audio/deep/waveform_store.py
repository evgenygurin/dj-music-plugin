from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import soundfile as sf


class StorageUploader(Protocol):
    async def upload(
        self,
        bucket: str,
        path: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> Any: ...


def build_waveform(audio_path: Path, n_points: int = 1000) -> list[float]:
    audio, _sr = sf.read(str(audio_path))
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    hop = max(1, len(audio) // n_points)
    peaks = []
    for i in range(n_points):
        segment = audio[i * hop : (i + 1) * hop]
        peak = float(np.max(np.abs(segment))) if len(segment) > 0 else 0.0
        peaks.append(round(peak, 6))

    max_peak = max(peaks) if peaks else 1.0
    if max_peak > 0:
        peaks = [p / max_peak for p in peaks]

    return peaks


async def upload_waveform(
    storage: StorageUploader,
    track_id: int,
    stem_name: str,
    peaks: list[float],
    duration_ms: int = 0,
) -> None:
    payload = {
        "track_id": track_id,
        "stem": stem_name,
        "duration_ms": duration_ms,
        "n_points": len(peaks),
        "peaks": peaks,
    }
    prefix = f"{track_id}" if stem_name == "original" else f"{track_id}/stem_{stem_name}"
    await storage.upload(
        bucket="track-waveforms",
        path=f"{prefix}/waveform.json",
        data=json.dumps(payload).encode(),
        content_type="application/json",
    )
