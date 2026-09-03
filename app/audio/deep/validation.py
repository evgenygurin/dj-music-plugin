from __future__ import annotations

from pathlib import Path

import numpy as np

from app.audio.deep.errors import StemOutputValidationError
from app.audio.deep.models import AudioMetadata, StemValidationResult

DURATION_TOLERANCE_SECONDS = 0.25
MIN_ARTIFACT_BYTES = 512


def validate_stem(
    path: Path,
    source: AudioMetadata,
    *,
    check_duration: bool = True,
) -> StemValidationResult:
    if not path.is_file():
        return StemValidationResult(False, str(path), reason="missing")
    if path.stat().st_size < MIN_ARTIFACT_BYTES:
        return StemValidationResult(False, str(path), reason="too_small")
    try:
        import soundfile as sf

        info = sf.info(str(path))
        if info.channels != source.channels:
            return StemValidationResult(False, str(path), info.samplerate, info.channels, info.frames, reason="channel_mismatch")
        if check_duration and abs(info.frames / info.samplerate - source.duration) > DURATION_TOLERANCE_SECONDS:
            return StemValidationResult(False, str(path), info.samplerate, info.channels, info.frames, reason="duration_mismatch")
        data, _ = sf.read(str(path), always_2d=True, dtype="float32")
    except Exception as exc:
        return StemValidationResult(False, str(path), reason=f"decode_failed:{exc}")

    if not np.isfinite(data).all():
        return StemValidationResult(False, str(path), info.samplerate, info.channels, info.frames, reason="non_finite")
    rms = float(np.sqrt(np.mean(np.square(data), dtype=np.float64))) if data.size else 0.0
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    if peak == 0.0:
        return StemValidationResult(False, str(path), info.samplerate, info.channels, info.frames, rms, peak, "all_zero")
    return StemValidationResult(True, str(path), info.samplerate, info.channels, info.frames, rms, peak)


def require_valid_stem(path: Path, source: AudioMetadata) -> StemValidationResult:
    result = validate_stem(path, source)
    if not result.valid:
        raise StemOutputValidationError(f"Invalid stem output {path}: {result.reason}")
    return result
