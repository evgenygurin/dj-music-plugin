"""Pure dataclasses for the render engine — no IO, no librosa, no ffmpeg."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TrackInput:
    """One set-version track as the engine needs it (pulled from the DB)."""

    track_id: int
    yandex_id: int | None
    title: str
    bpm: float
    key_code: int | None
    mix_in_ms: int
    integrated_lufs: float | None
    file_path: str

    def tempo_ratio(self, target_bpm: float) -> float:
        """Stretch ratio to reach ``target_bpm`` (>1 speeds a slow track up)."""
        return target_bpm / self.bpm


@dataclass(frozen=True, slots=True)
class BeatgridEntry:
    """Per-track kick anchor + QA corrections (the beatgrid.json row)."""

    track_id: int
    trim_start_s: float
    refined_trim_s: float | None
    gain_db: float
    phase_ms: float

    @property
    def effective_trim(self) -> float:
        """Refined kick trim when QA ran, else the raw kick anchor."""
        return self.refined_trim_s if self.refined_trim_s is not None else self.trim_start_s


@dataclass(frozen=True, slots=True)
class TrackSegment:
    """A track placed on the mix timeline (stretched, kick-aligned)."""

    index: int
    track_id: int
    file_path: str
    tempo_ratio: float
    trim_start_s: float
    gain_db: float
    body_bars: int
    d_in_s: float
    d_out_s: float
    length_s: float
    start_s: float


@dataclass(frozen=True, slots=True)
class RenderPlan:
    """A fully-resolved render: ordered segments + DSP constants."""

    target_bpm: float
    xsplit_hz: int
    low_swap_beats: float
    outro_fade_bars: int
    limiter_ceiling: float
    segments: list[TrackSegment] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.segments)
