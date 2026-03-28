"""Core audio data types — immutable, type-safe.

These types are the foundation of the audio analysis pipeline.
Used across all layers: core, analyzers, pipeline, services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class FrameParams:
    """Immutable frame/hop configuration. Single source of truth.

    Replaces hardcoded frame_length=2048, hop_length=512 in 3 files.
    """

    frame_length: int = 2048
    hop_length: int = 512


@dataclass
class AudioSignal:
    """Mono audio signal loaded once per pipeline run."""

    samples: np.ndarray  # mono float32
    sample_rate: int
    duration_seconds: float
    file_path: str = ""


@dataclass
class AnalyzerResult:
    """Result from a single analyzer run."""

    analyzer_name: str
    features: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str | None = None
