from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

StemName = Literal["vocals", "drums", "bass", "harmonic", "percussion"]
CANONICAL_STEMS: tuple[StemName, ...] = ("vocals", "drums", "bass", "harmonic", "percussion")
NATIVE_DEMUCS_STEMS: tuple[str, ...] = ("vocals", "drums", "bass", "other")


@dataclass(frozen=True, slots=True)
class SeparationOptions:
    model: str = "htdemucs"
    shifts: int = 1
    overlap: float = 0.25
    batch_size: int = 1
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class AudioMetadata:
    sample_rate: int
    channels: int
    samples: int

    @property
    def duration(self) -> float:
        return self.samples / self.sample_rate


@dataclass(frozen=True, slots=True)
class StemValidationResult:
    valid: bool
    path: str
    sample_rate: int | None = None
    channels: int | None = None
    samples: int | None = None
    rms: float | None = None
    peak: float | None = None
    reason: str | None = None
