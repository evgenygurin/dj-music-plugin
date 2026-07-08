"""DJ-specific manifest: track sources + render plan metadata."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DJSource:
    """One track in the DJ set version."""

    track_id: int
    file_path: str
    title: str
    bpm: float
    key_code: int | None


@dataclass(frozen=True, slots=True)
class DJManifest:
    """Build plan for one DJ set version."""

    version_id: int
    target_bpm: float
    sources: list[DJSource] = field(default_factory=list)
    n_segments: int = 0
    expected_duration_s: float = 0.0
    segment_start_s: list[float] = field(default_factory=list)
    segment_lengths_s: list[float] = field(default_factory=list)
