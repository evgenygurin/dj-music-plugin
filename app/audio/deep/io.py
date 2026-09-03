from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np

from app.audio.deep.errors import AudioInputError, StemEncodingError
from app.audio.deep.models import AudioMetadata

TARGET_SAMPLE_RATE = 44_100
TARGET_CHANNELS = 2


def _as_channels_first(data: np.ndarray) -> np.ndarray:
    array = np.asarray(data, dtype=np.float32)
    if array.ndim == 1:
        return array[None, :]
    if array.ndim != 2:
        raise AudioInputError(f"Unsupported audio shape: {array.shape}")
    if array.shape[0] <= 2 and array.shape[1] > array.shape[0]:
        return array
    if array.shape[1] <= 2:
        return array.T
    raise AudioInputError(f"Cannot infer channel layout from shape: {array.shape}")


def load_audio(path: Path) -> tuple[np.ndarray, AudioMetadata]:
    """Decode audio without manufacturing data when decoding fails."""
    if not path.is_file():
        raise AudioInputError(f"Audio input does not exist: {path}")
    try:
        import soundfile as sf

        data, sample_rate = sf.read(str(path), always_2d=False, dtype="float32")
    except Exception as exc:
        raise AudioInputError(f"Unable to decode audio input {path}: {exc}") from exc

    channels_first = _as_channels_first(data)
    if channels_first.shape[0] == 1:
        channels_first = np.repeat(channels_first, TARGET_CHANNELS, axis=0)
    elif channels_first.shape[0] > TARGET_CHANNELS:
        channels_first = channels_first[:TARGET_CHANNELS]
    if not np.isfinite(channels_first).all():
        raise AudioInputError(f"Audio input contains NaN/Inf samples: {path}")
    return channels_first, AudioMetadata(int(sample_rate), int(channels_first.shape[0]), int(channels_first.shape[1]))


def write_flac_atomic(path: Path, data: np.ndarray, sample_rate: int = TARGET_SAMPLE_RATE) -> None:
    """Write FLAC to a temporary file and atomically publish it."""
    array = _as_channels_first(data)
    if not np.isfinite(array).all():
        raise StemEncodingError(f"Cannot encode non-finite audio: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        import soundfile as sf

        sf.write(str(tmp_path), array.T, sample_rate, format="FLAC", subtype="PCM_16")
        os.replace(tmp_path, path)
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        raise StemEncodingError(f"Unable to encode FLAC {path}: {exc}") from exc
