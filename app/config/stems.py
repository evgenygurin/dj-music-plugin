"""Stems separation settings (Demucs / MLX / ONNX)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    pass


class StemsConfig(BaseSettings):
    """Configuration for stem separation.

    Env prefix ``DJ_STEMS_`` — e.g. ``DJ_STEMS_RUNTIME=onnx``,
    ``DJ_STEMS_SEGMENT=7.8``.

    Defaults target M2 8GB: ``segment=7.8`` (HTDemucs Transformer limit),
    ``jobs=0`` (single-process, no fork pressure), ``overlap=0.25``.
    """

    model_config = SettingsConfigDict(
        env_prefix="DJ_STEMS_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    runtime: Literal["auto", "mlx", "onnx", "torch"] = Field(
        default="auto",
        description="Preferred runtime: auto detects mlx→onnx→torch→cpu.",
    )
    model: str = Field(default="htdemucs", description="Demucs model name.")
    shifts: int = Field(
        default=5, ge=0, le=10, description="Demucs shifts (equivariant stabilization)."
    )
    overlap: float = Field(default=0.25, ge=0.0, le=0.95, description="Overlap between segments.")
    segment: float = Field(
        default=7.8, gt=0, le=7.8, description="Chunk length in seconds (HTDemucs ≤7.8)."
    )
    jobs: int = Field(default=0, ge=0, le=8, description="Parallel jobs (0 on 8GB).")
    fp16: bool = Field(default=True, description="Use fp16 weights where supported.")


class StemRunner(Protocol):
    """Protocol for stem separation runners (torch / onnx / mlx)."""

    def __call__(
        self,
        input_path: Path,
        cache_root: Path,
        *,
        model: str | None = None,
        flac: bool = False,
    ) -> dict[str, Path]: ...


def detect_runtime() -> Literal["mlx", "onnx", "torch", "cpu"]:
    """Detect best available runtime for stem separation.

    Priority: explicit ``DJ_STEMS_RUNTIME`` env (when not ``auto``) →
    ``mlx`` (if importable) → ``onnx`` (onnxruntime) → ``torch``
    (any torch install) → ``cpu`` fallback.

    Returns:
        One of ``mlx``, ``onnx``, ``torch``, ``cpu``.
    """
    env_runtime = os.environ.get("DJ_STEMS_RUNTIME", "auto").strip().lower()
    if env_runtime in ("mlx", "onnx", "torch"):
        return env_runtime  # type: ignore[return-value]
    if env_runtime == "cpu":
        return "cpu"

    # auto — probe in priority order
    try:
        import mlx.core  # type: ignore[import-not-found, unused-ignore]  # noqa: F401

        return "mlx"
    except Exception:
        pass

    try:
        import onnxruntime  # type: ignore[import-not-found, unused-ignore]  # noqa: F401

        return "onnx"
    except Exception:
        pass

    try:
        import torch  # type: ignore[import-not-found, unused-ignore]  # noqa: F401

        return "torch"
    except Exception:
        pass

    return "cpu"
