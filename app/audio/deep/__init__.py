"""Deep stem separation runtime selection."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.config.stems import StemRunner, StemsConfig, detect_runtime

STEMS_SEMAPHORE: asyncio.Semaphore = asyncio.Semaphore(1)

__all__ = ["STEMS_SEMAPHORE", "get_runner"]


def get_runner(cfg: StemsConfig | None = None) -> StemRunner:
    """Return a runner using explicit or capability-based runtime policy."""
    cfg = cfg or StemsConfig()
    explicit = cfg.runtime != "auto"
    runtime = cfg.runtime if explicit else detect_runtime()

    if runtime == "mlx":
        from app.audio.deep.demucs_mlx_runner import mlx_backend_available, mlx_separate

        if not mlx_backend_available():
            if explicit:
                raise RuntimeError("MLX backend requested but demucs-mlx/MLX is unavailable")
            runtime = "onnx"
        else:

            def _mlx_runner(
                input_path: Path,
                cache_root: Path,
                *,
                model: str | None = None,
                flac: bool = False,
            ) -> dict[str, Path]:
                return mlx_separate(
                    input_path,
                    cache_root,
                    model=model,
                    flac=flac,
                    shifts=cfg.shifts,
                    overlap=cfg.overlap,
                    segment=cfg.segment,
                    batch_size=1,
                )

            _mlx_runner.__name__ = "mlx_separate"
            return _mlx_runner

    if runtime == "onnx":
        try:
            from app.audio.deep.demucs_onnx_runner import onnx_separate
        except Exception as exc:
            if explicit:
                raise RuntimeError("ONNX backend requested but unavailable") from exc
            runtime = "torch"
        else:

            def _onnx_runner(
                input_path: Path,
                cache_root: Path,
                *,
                model: str | None = None,
                flac: bool = False,
            ) -> dict[str, Path]:
                return onnx_separate(
                    input_path,
                    cache_root,
                    stems=("vocals", "drums", "bass", "harmonic", "percussion"),
                    model=model,
                    flac=flac,
                )

            _onnx_runner.__name__ = "onnx_separate"
            return _onnx_runner

    if runtime in ("torch", "cpu"):
        try:
            from app.audio.deep.demucs_runner import run_demucs
        except Exception as exc:
            if explicit:
                raise RuntimeError("Torch backend requested but unavailable") from exc
            raise
        return run_demucs

    raise RuntimeError(f"Unsupported stem runtime: {runtime!r}")
