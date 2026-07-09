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
    xsplit_low_hz: int
    xsplit_high_hz: int
    eq_phase_1_ratio: float
    eq_phase_2_ratio: float
    low_swap_beats: float
    outro_fade_bars: int
    limiter_ceiling: float
    hpf_cutoff_hz: float = 30.0
    per_track_eq_mid_cut_db: float = -1.0
    per_track_eq_bright_boost_db: float = 1.5
    pre_comp_threshold_db: float = -18.0
    pre_comp_ratio: float = 3.0
    pre_comp_attack_ms: float = 10.0
    pre_comp_release_ms: float = 80.0
    glue_comp_threshold_db: float = -14.0
    glue_comp_ratio: float = 3.0
    glue_comp_attack_ms: float = 30.0
    glue_comp_release_ms: float = 150.0
    master_eq_air_boost_db: float = 1.5
    master_eq_mud_cut_db: float = -1.0
    master_eq_sub_boost_db: float = 0.5
    limiter_attack_ms: float = 10.0
    limiter_release_ms: float = 30.0
    dynaudnorm_maxgain: float = 2.0
    segments: list[TrackSegment] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.segments)
