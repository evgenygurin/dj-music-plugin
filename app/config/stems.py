"""Stem separation settings and runtime capability detection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

RuntimeName = Literal["auto", "mlx", "onnx", "torch", "cpu"]


class StemsConfig(BaseSettings):
    """Configuration for Demucs stem separation."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_STEMS_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    runtime: RuntimeName = Field(
        default="auto",
        description="Runtime: auto (MLX→ONNX→Torch), or an explicit backend.",
    )
    model: str = Field(default="htdemucs", description="Demucs model name.")
    shifts: int = Field(default=1, ge=0, le=10, description="Demucs shift averaging rounds.")
    overlap: float = Field(default=0.25, ge=0.0, le=0.95, description="Segment overlap ratio.")
    segment: float = Field(
        default=7.8, gt=0, le=7.8, description="HTDemucs maximum segment length."
    )
    jobs: int = Field(
        default=0, ge=0, le=8, description="Parallel CPU jobs; 0 avoids extra process pressure."
    )
    fp16: bool = Field(default=True, description="Use fp16 where supported by the backend.")


class StemRunner(Protocol):
    def __call__(
        self,
        input_path: Path,
        cache_root: Path,
        *,
        model: str | None = None,
        flac: bool = False,
    ) -> dict[str, Path]: ...


def _mlx_available() -> bool:
    try:
        from app.audio.deep.demucs_mlx_runner import mlx_backend_available

        return mlx_backend_available()
    except Exception:
        return False


def _onnx_available() -> bool:
    try:
        import onnxruntime  # type: ignore[import-not-found, unused-ignore]  # noqa: F401
    except Exception:
        return False
    return True


def _torch_available() -> bool:
    try:
        import torch  # type: ignore[import-not-found, unused-ignore]  # noqa: F401
    except Exception:
        return False
    return True


def detect_runtime() -> RuntimeName:
    """Select the first usable backend, not merely an installed framework."""
    env_runtime = os.environ.get("DJ_STEMS_RUNTIME", "auto").strip().lower()
    if env_runtime in {"mlx", "onnx", "torch", "cpu"}:
        return env_runtime  # type: ignore[return-value]

    if _mlx_available():
        return "mlx"
    if _onnx_available():
        return "onnx"
    if _torch_available():
        return "torch"
    return "cpu"
