from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.audio.deep.cache import cache_directory
from app.audio.deep.errors import (
    AudioInputError,
    StemBackendUnavailableError,
    StemInferenceError,
    StemModelLoadError,
    StemOutputValidationError,
)
from app.audio.deep.io import TARGET_SAMPLE_RATE, write_flac_atomic
from app.audio.deep.models import CANONICAL_STEMS, AudioMetadata, SeparationOptions
from app.audio.deep.postprocess import derive_percussion
from app.audio.deep.validation import require_valid_stem, validate_stem

logger = logging.getLogger(__name__)

DEFAULT_MLX_MODEL = "htdemucs"
DEMUCS_SEGMENT = 7.8
DEMUCS_OVERLAP = 0.25
PERCUSSION_SPLIT_HZ = 2_000
FLAC_COMPRESSION = 8
PIPELINE_VERSION = "2"


def mlx_backend_available() -> bool:
    try:
        import mlx.core  # type: ignore[import-not-found]  # noqa: F401
    except Exception:
        return False
    return True


def _require_backend() -> None:
    try:
        import mlx.core as mx
    except Exception as exc:
        raise StemBackendUnavailableError(
            "MLX stem backend is unavailable; install a compatible demucs-mlx/MLX pair."
        ) from exc
    try:
        mx.set_default_device(mx.gpu)
    except Exception:
        logger.debug("Could not set MLX default device to GPU", exc_info=True)


@lru_cache(maxsize=4)
def _get_separator(options: SeparationOptions) -> Any:
    _require_backend()
    try:
        from demucs_mlx import Separator  # type: ignore[import-not-found]

        return Separator(
            model=options.model,
            shifts=options.shifts,
            overlap=options.overlap,
            segment=options.segment,
            batch_size=options.batch_size,
            seed=options.seed,
        )
    except Exception as exc:
        raise StemModelLoadError(
            f"Unable to load MLX Demucs model {options.model!r}: {exc}"
        ) from exc


def _to_numpy(audio: Any) -> np.ndarray:
    try:
        array = np.asarray(audio, dtype=np.float32)
    except Exception as exc:
        raise StemInferenceError(f"Unable to materialize MLX audio output: {exc}") from exc
    if array.ndim == 1:
        array = array[None, :]
    if array.ndim != 2:
        raise StemInferenceError(f"Unexpected separated audio shape: {array.shape}")
    if array.shape[0] > 2 and array.shape[1] <= 2:
        array = array.T
    if array.shape[0] == 1:
        array = np.repeat(array, 2, axis=0)
    if array.shape[0] != 2:
        raise StemInferenceError(f"Expected mono/stereo output, got shape {array.shape}")
    if not np.isfinite(array).all():
        raise StemInferenceError("MLX produced NaN/Inf samples")
    return array


def _expected_paths(stem_dir: Path) -> dict[str, Path]:
    return {name: stem_dir / f"{name}.flac" for name in CANONICAL_STEMS}


def _validate_cached_paths(paths: dict[str, Path]) -> bool:
    for path in paths.values():
        result = validate_stem(path, AudioMetadata(TARGET_SAMPLE_RATE, 2, 0), check_duration=False)
        if not result.valid:
            return False
    return True


def _write_outputs(
    stems: dict[str, np.ndarray],
    stem_dir: Path,
    sample_rate: int,
    source_samples: int,
) -> dict[str, Path]:
    if not any(float(np.max(np.abs(stem))) > 0.0 for stem in stems.values()):
        raise StemOutputValidationError("Invalid MLX separation output: all native stems are zero")

    paths = _expected_paths(stem_dir)
    for name in ("vocals", "drums", "bass", "harmonic"):
        write_flac_atomic(paths[name], stems[name], sample_rate)

    derive_percussion(paths["drums"], paths["percussion"], sample_rate)
    source = AudioMetadata(sample_rate, 2, source_samples)
    for path in paths.values():
        require_valid_stem(path, source)
    return paths


def mlx_separate(
    input_path: Path,
    cache_root: Path,
    *,
    model: str | None = None,
    flac: bool = True,
    shifts: int = 1,
    overlap: float = DEMUCS_OVERLAP,
    segment: float = DEMUCS_SEGMENT,
    batch_size: int = 1,
    seed: int | None = None,
) -> dict[str, Path]:
    """Separate a track using native demucs-mlx and publish validated stems.

    Segmentation, overlap-add, resampling and MLX execution stay inside the
    native backend. This adapter handles project cache and canonical outputs.
    """
    if not input_path.is_file():
        raise AudioInputError(f"Audio input does not exist: {input_path}")
    if not flac:
        raise ValueError("MLX runner currently supports FLAC output only")
    if shifts < 0 or overlap < 0 or overlap >= 1 or batch_size < 1:
        raise ValueError("Invalid MLX separation options")
    if segment <= 0 or segment > DEMUCS_SEGMENT:
        raise ValueError(f"MLX segment must be in (0, {DEMUCS_SEGMENT}]")

    options = SeparationOptions(
        model=model or DEFAULT_MLX_MODEL,
        shifts=shifts,
        overlap=overlap,
        segment=segment,
        batch_size=batch_size,
        seed=seed,
    )
    stem_dir = cache_directory(
        cache_root, input_path, options.model, f"{PIPELINE_VERSION}:{options}"
    )
    paths = _expected_paths(stem_dir)
    if all(path.exists() for path in paths.values()) and _validate_cached_paths(paths):
        return paths
    for path in paths.values():
        path.unlink(missing_ok=True)

    separator = _get_separator(options)
    try:
        origin, raw_stems = separator.separate_audio_file(str(input_path), return_mx=True)
    except Exception as exc:
        raise StemInferenceError(f"MLX Demucs inference failed for {input_path}: {exc}") from exc

    origin_np = _to_numpy(origin)
    try:
        native = {
            name: _to_numpy(raw_stems[name]) for name in ("vocals", "drums", "bass", "other")
        }
    except (KeyError, StemInferenceError) as exc:
        raise StemInferenceError(f"MLX returned an invalid stem set: {exc}") from exc

    sample_rate = int(getattr(separator, "samplerate", TARGET_SAMPLE_RATE))
    source_samples = int(origin_np.shape[1])
    canonical = {
        "vocals": native["vocals"],
        "drums": native["drums"],
        "bass": native["bass"],
        "harmonic": native["other"],
    }
    logger.info(
        "MLX separation completed input=%s model=%s shifts=%d overlap=%.3f segment=%.2f samples=%d sr=%d",
        input_path,
        options.model,
        options.shifts,
        options.overlap,
        options.segment,
        source_samples,
        sample_rate,
    )
    return _write_outputs(canonical, stem_dir, sample_rate, source_samples)
