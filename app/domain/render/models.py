"""Pure dataclasses for the render engine — no IO, no librosa, no ffmpeg."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config.render import RenderSettings
    from app.domain.render.request import RenderRequest

# Prepared stem order — the default source of truth for ffmpeg input ordering
# (5 ``-i`` per track) and the stem filtergraph. Never reorder.
STEM_ORDER: tuple[str, ...] = ("drums", "bass", "harmonic", "instrumental", "acappella")

# Demucs' native 4-stem order. On-demand separation uses this to preserve the
# pre-refactor render balance instead of duplicating ``other`` as two inputs.
DEMUCS_STEM_ORDER: tuple[str, ...] = ("drums", "bass", "vocals", "other")


class RenderMode(str, Enum):  # noqa: UP042 - keep `str, Enum` for broader compat
    """Render pipeline selector — see :class:`RenderPlan.mode`."""

    CLASSIC = "classic"
    STEM = "stem"


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
    duration_ms: int | None = None

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
class StemSegment:
    """One track on the prepared-stem multi-deck timeline."""

    index: int
    track_idx: int
    track_id: int
    stem_paths: dict[str, str]
    tempo_ratio: float
    trim_start_s: float
    gain_db: float
    body_bars: int
    d_in_s: float
    d_out_s: float
    length_s: float
    start_s: float
    target_bpm: float
    low_swap_beats: float = 1.0
    eq_phase_1_ratio: float = 0.40
    eq_phase_2_ratio: float = 0.70
    bass_swap_ratio: float = 0.70


@dataclass(frozen=True, slots=True)
class RenderPlan:
    """A fully-resolved render: ordered segments + DSP constants.

    Support two modes:
    - Classic: ``segments`` with asplit-based EQ bass-swap (2-deck).
    - Stem: ``stem_segments`` with demucs stems (multi-deck, per-stem transitions).
    """

    target_bpm: float
    xsplit_low_hz: int
    xsplit_high_hz: int
    eq_phase_1_ratio: float
    eq_phase_2_ratio: float
    low_swap_beats: float
    outro_fade_bars: int
    limiter_ceiling: float
    mode: RenderMode = RenderMode.CLASSIC
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
    stem_segments: list[StemSegment] | None = None
    stem_order: tuple[str, ...] = STEM_ORDER
    # ── effects (set-wide, one preset per render) ──
    filter_sweep_preset: str | None = None
    echo_preset: str | None = None
    crossfade_curve_out: str = "tri"
    crossfade_curve_in: str = "exp"
    reverb_preset: str | None = None
    reverb_mix: float = 0.25

    @property
    def n(self) -> int:
        if self.stem_segments:
            return len(self.stem_segments)
        return len(self.segments)

    @classmethod
    def from_settings(
        cls,
        settings: RenderSettings,
        request: RenderRequest,
        *,
        segments: list[TrackSegment] | None = None,
        stem_segments: list[StemSegment] | None = None,
        stem_order: tuple[str, ...] = STEM_ORDER,
    ) -> RenderPlan:
        """Factory: DSP constants from ``settings``, effects from ``request``."""
        return cls(
            mode=request.mode,
            target_bpm=settings.target_bpm,
            xsplit_low_hz=settings.xsplit_low_hz,
            xsplit_high_hz=settings.xsplit_high_hz,
            eq_phase_1_ratio=settings.eq_phase_1_ratio,
            eq_phase_2_ratio=settings.eq_phase_2_ratio,
            low_swap_beats=settings.low_swap_beats,
            outro_fade_bars=settings.outro_fade_bars,
            limiter_ceiling=settings.limiter_ceiling,
            hpf_cutoff_hz=settings.hpf_cutoff_hz,
            per_track_eq_mid_cut_db=settings.per_track_eq_mid_cut_db,
            per_track_eq_bright_boost_db=settings.per_track_eq_bright_boost_db,
            pre_comp_threshold_db=settings.pre_comp_threshold_db,
            pre_comp_ratio=settings.pre_comp_ratio,
            pre_comp_attack_ms=settings.pre_comp_attack_ms,
            pre_comp_release_ms=settings.pre_comp_release_ms,
            glue_comp_threshold_db=settings.glue_comp_threshold_db,
            glue_comp_ratio=settings.glue_comp_ratio,
            glue_comp_attack_ms=settings.glue_comp_attack_ms,
            glue_comp_release_ms=settings.glue_comp_release_ms,
            master_eq_air_boost_db=settings.master_eq_air_boost_db,
            master_eq_mud_cut_db=settings.master_eq_mud_cut_db,
            master_eq_sub_boost_db=settings.master_eq_sub_boost_db,
            limiter_attack_ms=settings.limiter_attack_ms,
            limiter_release_ms=settings.limiter_release_ms,
            dynaudnorm_maxgain=settings.dynaudnorm_maxgain,
            segments=segments if segments is not None else [],
            stem_segments=stem_segments,
            stem_order=stem_order,
            filter_sweep_preset=request.filter_sweep,
            echo_preset=request.echo,
            crossfade_curve_out=request.crossfade_curve_out,
            crossfade_curve_in=request.crossfade_curve_in,
            reverb_preset=request.reverb,
            reverb_mix=request.reverb_mix,
        )
