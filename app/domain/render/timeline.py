"""Pure timeline math: place stretched, kick-aligned segments on one line.

Ported (numbers-preserving) from render_pipeline.py ``_segment_sequence`` + the
``render`` overlap loop + ``boundaries``. The placement geometry is computed
once (``place_segments``) and reused by the classic plan, the stem plan, and the
transition-window map — so the loop lives in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config.render import RenderSettings
from app.domain.render.models import (
    BeatgridEntry,
    RenderPlan,
    StemSegment,
    TrackInput,
    TrackSegment,
)


@dataclass(frozen=True, slots=True)
class TransitionWindow:
    from_index: int
    to_index: int
    start_s: float
    end_s: float


@dataclass(frozen=True, slots=True)
class TimelineWindows:
    segments: list[tuple[int, float, float]] = field(default_factory=list)  # (index, start, end)
    transitions: list[TransitionWindow] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SegmentGeometry:
    """Mode-agnostic placement of one track on the timeline.

    Everything the classic (:class:`TrackSegment`) and stem
    (:class:`StemSegment`) segments share; the mode-specific fields (file path /
    stem paths, EQ ratios) are attached by each plan builder.
    """

    index: int
    track_id: int
    tempo_ratio: float
    trim_start_s: float
    gain_db: float
    body_bars: int
    d_in_s: float
    d_out_s: float
    length_s: float
    start_s: float


def bar_seconds(target_bpm: float) -> float:
    """Length of one 4/4 bar (4 beats) at ``target_bpm``, in seconds."""
    return 4.0 * (60.0 / target_bpm)


def _transition_durations(
    n: int, transition_bars: int, bar_s: float, per_transition_bars: list[int] | None
) -> list[float]:
    """Per-transition length D_i (seconds) between segment i and i+1."""
    if per_transition_bars is not None and len(per_transition_bars) == n - 1:
        return [tb * bar_s for tb in per_transition_bars]
    return [transition_bars * bar_s for _ in range(n - 1)]


def place_segments(
    inputs: list[TrackInput],
    grid: dict[int, BeatgridEntry],
    *,
    target_bpm: float,
    body_bars: int,
    transition_bars: int,
    per_transition_bars: list[int] | None = None,
    per_body_bars: list[int] | None = None,
) -> list[SegmentGeometry]:
    """Resolve ordered inputs + beatgrid into placed, overlap-aware geometries."""
    bar_s = bar_seconds(target_bpm)
    n = len(inputs)
    d = _transition_durations(n, transition_bars, bar_s, per_transition_bars)
    geometries: list[SegmentGeometry] = []
    running_t = 0.0
    for i, ti in enumerate(inputs):
        d_in = d[i - 1] if i > 0 else 0.0
        d_out = d[i] if i < n - 1 else 0.0
        seg_body = (
            per_body_bars[i] if per_body_bars is not None and i < len(per_body_bars) else body_bars
        )
        length = seg_body * bar_s + d_in + d_out
        g = grid.get(ti.track_id)
        geometries.append(
            SegmentGeometry(
                index=i,
                track_id=ti.track_id,
                tempo_ratio=ti.tempo_ratio(target_bpm),
                trim_start_s=g.effective_trim if g is not None else 0.0,
                gain_db=g.gain_db if g is not None else 0.0,
                body_bars=seg_body,
                d_in_s=d_in,
                d_out_s=d_out,
                length_s=length,
                start_s=running_t,
            )
        )
        running_t += length - d_out
    return geometries


def build_render_plan(
    inputs: list[TrackInput],
    grid: dict[int, BeatgridEntry],
    *,
    target_bpm: float,
    body_bars: int,
    transition_bars: int,
    xsplit_low_hz: int,
    xsplit_high_hz: int,
    eq_phase_1_ratio: float,
    eq_phase_2_ratio: float,
    low_swap_beats: float,
    outro_fade_bars: int,
    limiter_ceiling: float,
    per_transition_bars: list[int] | None = None,
    per_body_bars: list[int] | None = None,
    filter_sweep_preset: str | None = None,
    echo_preset: str | None = None,
    crossfade_curve_out: str = "tri",
    crossfade_curve_in: str = "exp",
    reverb_preset: str | None = None,
    reverb_mix: float = 0.25,
) -> RenderPlan:
    """Classic single-file-per-track plan (asplit 3-band EQ bass-swap)."""
    geometries = place_segments(
        inputs,
        grid,
        target_bpm=target_bpm,
        body_bars=body_bars,
        transition_bars=transition_bars,
        per_transition_bars=per_transition_bars,
        per_body_bars=per_body_bars,
    )
    segments = [
        TrackSegment(
            index=g.index,
            track_id=g.track_id,
            file_path=inputs[g.index].file_path,
            tempo_ratio=g.tempo_ratio,
            trim_start_s=g.trim_start_s,
            gain_db=g.gain_db,
            body_bars=g.body_bars,
            d_in_s=g.d_in_s,
            d_out_s=g.d_out_s,
            length_s=g.length_s,
            start_s=g.start_s,
        )
        for g in geometries
    ]
    return RenderPlan.from_settings(
        RenderSettings(),
        target_bpm=target_bpm,
        xsplit_low_hz=xsplit_low_hz,
        xsplit_high_hz=xsplit_high_hz,
        eq_phase_1_ratio=eq_phase_1_ratio,
        eq_phase_2_ratio=eq_phase_2_ratio,
        low_swap_beats=low_swap_beats,
        outro_fade_bars=outro_fade_bars,
        limiter_ceiling=limiter_ceiling,
        segments=segments,
        filter_sweep_preset=filter_sweep_preset,
        echo_preset=echo_preset,
        crossfade_curve_out=crossfade_curve_out,
        crossfade_curve_in=crossfade_curve_in,
        reverb_preset=reverb_preset,
        reverb_mix=reverb_mix,
    )


def build_stem_render_plan(
    inputs: list[TrackInput],
    stem_paths_by_track: dict[int, dict[str, str]],
    grid: dict[int, BeatgridEntry],
    *,
    target_bpm: float,
    body_bars: int,
    transition_bars: int,
    xsplit_low_hz: int,
    xsplit_high_hz: int,
    eq_phase_1_ratio: float,
    eq_phase_2_ratio: float,
    low_swap_beats: float,
    outro_fade_bars: int,
    limiter_ceiling: float,
    per_transition_bars: list[int] | None = None,
    per_body_bars: list[int] | None = None,
    filter_sweep_preset: str | None = None,
    echo_preset: str | None = None,
    crossfade_curve_out: str = "tri",
    crossfade_curve_in: str = "exp",
    reverb_preset: str | None = None,
    reverb_mix: float = 0.25,
    bass_swap_ratio: float = 0.70,
) -> RenderPlan:
    """Prepared-stem multi-deck plan — each segment carries 5 stem paths."""
    geometries = place_segments(
        inputs,
        grid,
        target_bpm=target_bpm,
        body_bars=body_bars,
        transition_bars=transition_bars,
        per_transition_bars=per_transition_bars,
        per_body_bars=per_body_bars,
    )
    stem_segments = [
        StemSegment(
            index=g.index,
            track_idx=g.index,
            track_id=g.track_id,
            stem_paths=stem_paths_by_track.get(g.track_id, {}),
            tempo_ratio=g.tempo_ratio,
            trim_start_s=g.trim_start_s,
            gain_db=g.gain_db,
            body_bars=g.body_bars,
            d_in_s=g.d_in_s,
            d_out_s=g.d_out_s,
            length_s=g.length_s,
            start_s=g.start_s,
            target_bpm=target_bpm,
            low_swap_beats=low_swap_beats,
            eq_phase_1_ratio=eq_phase_1_ratio,
            eq_phase_2_ratio=eq_phase_2_ratio,
            bass_swap_ratio=bass_swap_ratio,
        )
        for g in geometries
    ]
    return RenderPlan.from_settings(
        RenderSettings(),
        target_bpm=target_bpm,
        xsplit_low_hz=xsplit_low_hz,
        xsplit_high_hz=xsplit_high_hz,
        eq_phase_1_ratio=eq_phase_1_ratio,
        eq_phase_2_ratio=eq_phase_2_ratio,
        low_swap_beats=low_swap_beats,
        outro_fade_bars=outro_fade_bars,
        limiter_ceiling=limiter_ceiling,
        stem_segments=stem_segments,
        filter_sweep_preset=filter_sweep_preset,
        echo_preset=echo_preset,
        crossfade_curve_out=crossfade_curve_out,
        crossfade_curve_in=crossfade_curve_in,
        reverb_preset=reverb_preset,
        reverb_mix=reverb_mix,
    )


def timeline_windows(
    inputs: list[TrackInput],
    *,
    target_bpm: float,
    body_bars: int,
    transition_bars: int,
    per_transition_bars: list[int] | None = None,
    per_body_bars: list[int] | None = None,
) -> TimelineWindows:
    """Map segments + transition windows onto the timeline (from ``boundaries``)."""
    geometries = place_segments(
        inputs,
        {},
        target_bpm=target_bpm,
        body_bars=body_bars,
        transition_bars=transition_bars,
        per_transition_bars=per_transition_bars,
        per_body_bars=per_body_bars,
    )
    segments = [(g.index, g.start_s, g.start_s + g.length_s) for g in geometries]
    transitions = [
        TransitionWindow(
            from_index=g.index - 1,
            to_index=g.index,
            start_s=g.start_s,
            end_s=g.start_s + g.d_in_s,
        )
        for g in geometries
        if g.index > 0
    ]
    return TimelineWindows(segments=segments, transitions=transitions)
