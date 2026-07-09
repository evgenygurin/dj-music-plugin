"""Pure timeline math: place stretched, kick-aligned segments on one line.

Ported verbatim (numbers-preserving) from render_pipeline.py:
``_segment_sequence`` + the ``render`` overlap loop + ``boundaries``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.render.models import BeatgridEntry, RenderPlan, TrackInput, TrackSegment


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


def _durations(n: int, transition_bars: int, bar_s: float) -> list[float]:
    """Per-transition length D_i (seconds) between segment i and i+1."""
    return [transition_bars * bar_s for _ in range(n - 1)]


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
) -> RenderPlan:
    """Resolve ordered inputs + beatgrid into a RenderPlan of placed segments."""
    bar_s = 4.0 * (60.0 / target_bpm)
    n = len(inputs)
    if per_transition_bars is not None and len(per_transition_bars) == n - 1:
        d = [tb * bar_s for tb in per_transition_bars]
    else:
        d = _durations(n, transition_bars, bar_s)
    segments: list[TrackSegment] = []
    running_t = 0.0
    for i, ti in enumerate(inputs):
        d_in = d[i - 1] if i > 0 else 0.0
        d_out = d[i] if i < n - 1 else 0.0
        seg_body = (
            per_body_bars[i] if per_body_bars is not None and i < len(per_body_bars) else body_bars
        )
        length = seg_body * bar_s + d_in + d_out
        g = grid.get(ti.track_id)
        trim = g.effective_trim if g is not None else 0.0
        gain = g.gain_db if g is not None else 0.0
        segments.append(
            TrackSegment(
                index=i,
                track_id=ti.track_id,
                file_path=ti.file_path,
                tempo_ratio=ti.tempo_ratio(target_bpm),
                trim_start_s=trim,
                gain_db=gain,
                body_bars=seg_body,
                d_in_s=d_in,
                d_out_s=d_out,
                length_s=length,
                start_s=running_t,
            )
        )
        running_t += length - d_out
    return RenderPlan(
        target_bpm=target_bpm,
        xsplit_low_hz=xsplit_low_hz,
        xsplit_high_hz=xsplit_high_hz,
        eq_phase_1_ratio=eq_phase_1_ratio,
        eq_phase_2_ratio=eq_phase_2_ratio,
        low_swap_beats=low_swap_beats,
        outro_fade_bars=outro_fade_bars,
        limiter_ceiling=limiter_ceiling,
        segments=segments,
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
    bar_s = 4.0 * (60.0 / target_bpm)
    n = len(inputs)
    if per_transition_bars is not None and len(per_transition_bars) == n - 1:
        d = [tb * bar_s for tb in per_transition_bars]
    else:
        d = _durations(n, transition_bars, bar_s)
    segs: list[tuple[int, float, float]] = []
    trans: list[TransitionWindow] = []
    running_t = 0.0
    starts: list[tuple[float, float]] = []  # (start, d_in)
    for i in range(n):
        d_in = d[i - 1] if i > 0 else 0.0
        d_out = d[i] if i < n - 1 else 0.0
        seg_body = (
            per_body_bars[i] if per_body_bars is not None and i < len(per_body_bars) else body_bars
        )
        length = seg_body * bar_s + d_in + d_out
        segs.append((i, running_t, running_t + length))
        starts.append((running_t, d_in))
        running_t += length - d_out
    for i in range(1, n):
        start, d_in = starts[i]
        trans.append(
            TransitionWindow(from_index=i - 1, to_index=i, start_s=start, end_s=start + d_in)
        )
    return TimelineWindows(segments=segs, transitions=trans)
