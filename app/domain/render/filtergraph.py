"""ffmpeg ``filter_complex`` construction — Template Method + Strategy.

Two render algorithms share one skeleton:

* :class:`FilterGraphBuilder` (**Template Method**) — ``build`` walks the placed
  segments, delegates each per-segment block to a subclass, then appends the one
  shared master bus (amix → master EQ → limiter).
* :class:`ClassicGraphBuilder` — single file per track, asplit 3-band EQ
  bass-swap (highs phase 1, mids phase 2, bass pinpoint swap phase 3).
  Supports filter_sweep and echo effects per RenderPlan config.
* :class:`StemGraphBuilder` — 5 prepared stems per track, staggered per-stem
  transitions with artifact-masking high-pass. This mode consumes already
  separated files and never runs source separation.
* :class:`RenderStrategy` (**Strategy**) — pairs a graph builder with its ffmpeg
  input expansion; :func:`select_strategy` picks the mode from the plan. The
  runner depends only on the strategy, so a new render mode is a new subclass —
  no edits to the runner or the handler (OCP).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.render.effects_resolver import EffectPresetResolver, ResolvedEffects
from app.domain.render.eq import build_master_eq
from app.domain.render.models import (
    STEM_ORDER,
    RenderMode,
    RenderPlan,
    StemSegment,
    TrackSegment,
)
from app.domain.render.stem_voicing import STEM_VOICING


@dataclass(frozen=True, slots=True)
class _FrameContext:
    plan: RenderPlan
    i: int
    seg: TrackSegment
    length: float
    bar_s: float
    beat_s: float
    low_x: float
    p1: float
    p2: float
    has_prev: bool
    has_next: bool
    curve_out: str
    curve_in: str
    n: int
    outro_fade_s: float

    @classmethod
    def from_segment(cls, plan: RenderPlan, i: int, seg: TrackSegment) -> _FrameContext:
        bar_s = 4.0 * (60.0 / plan.target_bpm)
        beat_s = 60.0 / plan.target_bpm
        return cls(
            plan=plan,
            i=i,
            seg=seg,
            length=seg.length_s,
            bar_s=bar_s,
            beat_s=beat_s,
            low_x=plan.low_swap_beats * beat_s,
            p1=plan.eq_phase_1_ratio,
            p2=plan.eq_phase_2_ratio,
            has_prev=i > 0,
            has_next=i < plan.n - 1,
            curve_out=plan.crossfade_curve_out,
            curve_in=plan.crossfade_curve_in,
            n=plan.n,
            outro_fade_s=min(plan.outro_fade_bars * bar_s, seg.length_s),
        )


class FilterGraphBuilder(ABC):
    """Template Method: per-segment blocks + one shared master bus."""

    def build(self, plan: RenderPlan) -> list[str]:
        """Return the ordered ``filter_complex`` statements (runner joins with ';')."""
        parts: list[str] = []
        mixlabels: list[str] = []
        for i, seg in enumerate(self._segments(plan)):
            block, label = self._segment_block(plan, i, seg)
            parts.extend(block)
            mixlabels.append(label)
        parts.append(self._master_bus(plan, mixlabels))
        return parts

    @abstractmethod
    def _segments(self, plan: RenderPlan) -> Sequence[object]:
        """The placed segments this builder consumes."""

    @abstractmethod
    def _segment_block(self, plan: RenderPlan, i: int, seg: object) -> tuple[list[str], str]:
        """Statements for one segment + its ``[m{i}]`` mix label."""

    def _master_bus(self, plan: RenderPlan, mixlabels: list[str]) -> str:
        """Shared master chain: mix all decks → master EQ → limiter → ``[mix]``."""
        master_eq = build_master_eq(
            plan.master_eq_mud_cut_db,
            plan.master_eq_air_boost_db,
            plan.master_eq_sub_boost_db,
        )
        return (
            "".join(mixlabels) + f"amix=inputs={len(mixlabels)}:normalize=0,"
            f"firequalizer=gain_entry='{master_eq}',"
            f"alimiter=level_in=1:level_out=1:limit={plan.limiter_ceiling}:"
            f"attack={plan.limiter_attack_ms}:release={plan.limiter_release_ms}:asc=0[mix]"
        )


class ClassicGraphBuilder(FilterGraphBuilder):
    """Single-file-per-track 3-band EQ bass-swap (highs → mids → bass pinpoint)."""

    _effects: EffectPresetResolver = EffectPresetResolver()

    def _segments(self, plan: RenderPlan) -> Sequence[TrackSegment]:
        return plan.segments

    def _segment_block(self, plan: RenderPlan, i: int, seg: object) -> tuple[list[str], str]:
        assert isinstance(seg, TrackSegment)
        ctx = _FrameContext.from_segment(plan, i, seg)
        fx = self._effects.resolve(plan)
        return [
            self._source_chain(ctx),
            *self._echo_split(ctx, fx),
            *self._band_split(ctx, fx),
            self._emit_high_band(ctx),
            self._emit_mid_band(ctx),
            self._emit_low_band(ctx),
            self._mix_segment(ctx, fx),
        ], f"[m{i}]"

    @staticmethod
    def _source_chain(ctx: _FrameContext) -> str:
        seg = ctx.seg
        return (
            f"[{ctx.i}:a]atrim=start={seg.trim_start_s:.4f}:"
            f"duration={ctx.length / seg.tempo_ratio + 1.0:.3f},"
            f"asetpts=PTS-STARTPTS,rubberband=tempo={seg.tempo_ratio:.5f}:pitchq=quality,"
            f"atrim=duration={ctx.length:.3f},asetpts=PTS-STARTPTS,volume={seg.gain_db:.2f}dB,"
            f"aformat=sample_rates=44100:channel_layouts=stereo[s{ctx.i}]"
        )

    @staticmethod
    def _echo_split(ctx: _FrameContext, fx: ResolvedEffects) -> list[str]:
        if fx.echo is None:
            return []

        echo_aecho = fx.echo.ffmpeg_aecho_expr()
        parts = [f"[s{ctx.i}]asplit=2[sd{ctx.i}][se{ctx.i}]"]
        if ctx.has_next:
            tail_start = max(0.0, ctx.length - ctx.seg.d_out_s * 0.3)
            tail_dur = min(ctx.seg.d_out_s * 0.3, ctx.length - tail_start)
            parts.append(
                f"[se{ctx.i}]atrim=start={tail_start:.3f}:duration={tail_dur:.3f},"
                f"asetpts=PTS-STARTPTS,"
                f"aecho={echo_aecho}[se{ctx.i}_out]"
            )
        else:
            parts.append(f"[se{ctx.i}]aecho={echo_aecho}[se{ctx.i}_out]")
        return parts

    @staticmethod
    def _band_split(ctx: _FrameContext, fx: ResolvedEffects) -> list[str]:
        sweep_expr = ""
        if fx.sweep is not None and fx.sweep.outgoing is not None and ctx.has_next:
            end_f = int(fx.sweep.outgoing.end_freq_hz)
            t_start = ctx.length - ctx.seg.d_out_s
            sweep_expr = f"lowpass=f={end_f}:enable='between(t,{t_start:.2f},{ctx.length:.2f})',"

        dry_in = f"[sd{ctx.i}]" if fx.echo is not None else f"[s{ctx.i}]"
        return [
            f"{dry_in}{sweep_expr}asplit=3[s{ctx.i}a][s{ctx.i}b][s{ctx.i}c]",
            f"[s{ctx.i}a]lowpass=f={ctx.plan.xsplit_low_hz}[lo{ctx.i}]",
            f"[s{ctx.i}b]highpass=f={ctx.plan.xsplit_low_hz},"
            f"lowpass=f={ctx.plan.xsplit_high_hz}[mid{ctx.i}]",
            f"[s{ctx.i}c]highpass=f={ctx.plan.xsplit_high_hz}[hi{ctx.i}]",
        ]

    def _emit_high_band(self, ctx: _FrameContext) -> str:
        fades = self._high_fades(ctx)
        return f"[hi{ctx.i}]{','.join(fades) if fades else 'acopy'}[H{ctx.i}]"

    def _emit_mid_band(self, ctx: _FrameContext) -> str:
        fades = self._mid_fades(ctx)
        return f"[mid{ctx.i}]{','.join(fades) if fades else 'acopy'}[MID{ctx.i}]"

    def _emit_low_band(self, ctx: _FrameContext) -> str:
        fades = self._low_fades(ctx)
        return f"[lo{ctx.i}]{','.join(fades) if fades else 'acopy'}[Lo{ctx.i}]"

    @staticmethod
    def _high_fades(ctx: _FrameContext) -> list[str]:
        fades: list[str] = []
        if ctx.has_prev:
            fades.append(
                f"afade=t=in:curve={ctx.curve_in}:st=0:d={ctx.seg.d_in_s * ctx.p1:.3f}"
            )
        if ctx.has_next:
            fades.append(
                f"afade=t=out:curve={ctx.curve_out}:st={ctx.length - ctx.seg.d_out_s:.3f}:"
                f"d={ctx.seg.d_out_s * ctx.p1:.3f}"
            )
        else:
            fades.append(
                f"afade=t=out:curve={ctx.curve_out}:st={ctx.length - ctx.outro_fade_s:.3f}:"
                f"d={ctx.outro_fade_s:.3f}"
            )
        return fades

    @staticmethod
    def _mid_fades(ctx: _FrameContext) -> list[str]:
        fades: list[str] = []
        if ctx.has_prev:
            fades.append(
                f"afade=t=in:curve={ctx.curve_in}:st={ctx.seg.d_in_s * ctx.p1:.3f}:"
                f"d={ctx.seg.d_in_s * (ctx.p2 - ctx.p1):.3f}"
            )
        if ctx.has_next:
            fades.append(
                f"afade=t=out:curve={ctx.curve_out}:"
                f"st={ctx.length - ctx.seg.d_out_s * (1.0 - ctx.p1):.3f}:"
                f"d={ctx.seg.d_out_s * (ctx.p2 - ctx.p1):.3f}"
            )
        else:
            fades.append(
                f"afade=t=out:curve={ctx.curve_out}:st={ctx.length - ctx.outro_fade_s:.3f}:"
                f"d={ctx.outro_fade_s:.3f}"
            )
        return fades

    @staticmethod
    def _low_fades(ctx: _FrameContext) -> list[str]:
        fades: list[str] = []
        if ctx.has_prev:
            st = ctx.seg.d_in_s * ctx.p2 - ctx.low_x / 2
            fades.append(f"afade=t=in:curve={ctx.curve_in}:st={st:.3f}:d={ctx.low_x:.3f}")
        if ctx.has_next:
            st = ctx.length - ctx.seg.d_out_s * (1.0 - ctx.p2) - ctx.low_x / 2
            fades.append(f"afade=t=out:curve={ctx.curve_out}:st={st:.3f}:d={ctx.low_x:.3f}")
        else:
            fades.append(
                f"afade=t=out:curve={ctx.curve_out}:st={ctx.length - ctx.outro_fade_s:.3f}:"
                f"d={ctx.outro_fade_s:.3f}"
            )
        return fades

    @staticmethod
    def _mix_segment(ctx: _FrameContext, fx: ResolvedEffects) -> str:
        t_ms = int(ctx.seg.start_s * 1000)
        if fx.echo is None:
            return (
                f"[H{ctx.i}][MID{ctx.i}][Lo{ctx.i}]amix=inputs=3:normalize=0,"
                f"adelay={t_ms}|{t_ms}|{t_ms}[m{ctx.i}]"
            )

        echo_w = max(0.1, min(0.5, min(0.25, fx.echo.wet_dry_ratio * 0.6)))
        return (
            f"[H{ctx.i}][MID{ctx.i}][Lo{ctx.i}]amix=inputs=3:normalize=0[sm{ctx.i}];"
            f"[sm{ctx.i}][se{ctx.i}_out]amix=inputs=2:normalize=0:weights=1 {echo_w:.2f},"
            f"adelay={t_ms}|{t_ms}[m{ctx.i}]"
        )


class StemGraphBuilder(FilterGraphBuilder):
    """5-stem multi-deck: staggered per-stem transitions + bleed-masking HPF.

    Staggered like the classic 3-band ritual: HARMONIC swaps early (p1), DRUMS
    ride the whole window (continuous drive), ACAPPELLA stays wide (p2), and
    BASS uses a 1-beat pinpoint swap at ``bass_swap_ratio``. INSTRUMENTAL is
    kept as a lower-gain safety bed so five prepared stems can sum cleanly.
    First track eases in, last fades out over ``outro_fade_bars``.
    """

    def _segments(self, plan: RenderPlan) -> Sequence[StemSegment]:
        assert plan.stem_segments is not None
        return plan.stem_segments

    def _segment_block(self, plan: RenderPlan, i: int, seg: object) -> tuple[list[str], str]:
        assert isinstance(seg, StemSegment)
        bar_s = 4.0 * (60.0 / plan.target_bpm)
        beat_s = 60.0 / plan.target_bpm
        has_prev = i > 0
        has_next = i < plan.n - 1
        low_x = seg.low_swap_beats * beat_s
        intro_d = min(bar_s, seg.length_s)
        outro_d = min(plan.outro_fade_bars * bar_s, seg.length_s)

        parts: list[str] = []
        faded: list[str] = []
        for stem in STEM_ORDER:
            input_idx = seg.track_idx * len(STEM_ORDER) + STEM_ORDER.index(stem)
            label = f"s{i}_{stem}"
            gain_db = seg.gain_db + STEM_VOICING[stem].gain_db
            parts.append(
                self._stem_chain(input_idx, seg, label, STEM_VOICING[stem].hpf_hz, gain_db)
            )
            fades = self._stem_fades(
                stem,
                seg,
                has_prev=has_prev,
                has_next=has_next,
                intro_d=intro_d,
                outro_d=outro_d,
                low_x=low_x,
            )
            parts.append(f"[{label}]{','.join(fades)}[{label}_faded]")
            faded.append(f"[{label}_faded]")

        t_ms = int(seg.start_s * 1000)
        parts.append(
            f"{''.join(faded)}amix=inputs={len(STEM_ORDER)}:normalize=0,"
            f"adelay={t_ms}|{t_ms}|{t_ms}[m{i}]"
        )
        return parts, f"[m{i}]"

    @staticmethod
    def _stem_chain(
        input_idx: int,
        seg: StemSegment,
        label: str,
        hpf_hz: int | None,
        gain_db: float,
    ) -> str:
        """One stem: trim → tempo-stretch → (optional HPF) → gain → format."""
        hpf = f"highpass=f={hpf_hz}," if hpf_hz else ""
        return (
            f"[{input_idx}:a]atrim=start={seg.trim_start_s:.4f}:"
            f"duration={seg.length_s / seg.tempo_ratio + 1.0:.3f},"
            f"asetpts=PTS-STARTPTS,rubberband=tempo={seg.tempo_ratio:.5f}:pitchq=quality,"
            f"atrim=duration={seg.length_s:.3f},asetpts=PTS-STARTPTS,"
            f"{hpf}volume={gain_db:.2f}dB,"
            f"aformat=sample_rates=44100:channel_layouts=stereo"
            f"[{label}]"
        )

    @staticmethod
    def _stem_fades(
        stem: str,
        seg: StemSegment,
        *,
        has_prev: bool,
        has_next: bool,
        intro_d: float,
        outro_d: float,
        low_x: float,
    ) -> list[str]:
        """Staggered in/out fades for one stem within its segment."""
        length = seg.length_s
        d_in, d_out = seg.d_in_s, seg.d_out_s
        p1, p2 = seg.eq_phase_1_ratio, seg.eq_phase_2_ratio
        fades: list[str] = []

        # ── fade IN (head) ──
        if not has_prev:
            fades.append(f"afade=t=in:curve=qsin:st=0:d={intro_d:.3f}")
        elif stem == "drums":
            fades.append(f"afade=t=in:curve=qsin:st=0:d={d_in:.3f}")
        elif stem in {"harmonic", "instrumental"}:
            fades.append(f"afade=t=in:curve=qsin:st=0:d={max(0.05, d_in * p1):.3f}")
        elif stem == "acappella":
            fades.append(f"afade=t=in:curve=qsin:st=0:d={max(0.05, d_in * p2):.3f}")
        else:  # bass — pinpoint swap
            st = max(0.0, d_in * seg.bass_swap_ratio - low_x / 2)
            fades.append(f"afade=t=in:curve=qsin:st={st:.3f}:d={low_x:.3f}")

        # ── fade OUT (tail) ──
        if not has_next:
            st = max(0.0, length - outro_d)
            fades.append(f"afade=t=out:curve=qsin:st={st:.3f}:d={outro_d:.3f}")
        elif stem == "drums":
            st = max(0.0, length - d_out)
            fades.append(f"afade=t=out:curve=qsin:st={st:.3f}:d={d_out:.3f}")
        elif stem in {"harmonic", "instrumental"}:
            dur = max(0.05, d_out * p1)
            fades.append(f"afade=t=out:curve=qsin:st={length - dur:.3f}:d={dur:.3f}")
        elif stem == "acappella":
            dur = max(0.05, d_out * p2)
            fades.append(f"afade=t=out:curve=qsin:st={length - dur:.3f}:d={dur:.3f}")
        else:  # bass — pinpoint swap
            st = max(0.0, length - d_out * (1.0 - seg.bass_swap_ratio) - low_x / 2)
            fades.append(f"afade=t=out:curve=qsin:st={st:.3f}:d={low_x:.3f}")

        return fades


class RenderStrategy(ABC):
    """Strategy: a graph builder + how to expand its ffmpeg ``-i`` inputs."""

    graph_builder: FilterGraphBuilder

    @abstractmethod
    def input_files(self, plan: RenderPlan) -> list[str]:
        """Ordered ffmpeg input files (one entry per ``-i``)."""

    def filtergraph(self, plan: RenderPlan) -> list[str]:
        return self.graph_builder.build(plan)


class ClassicEqStrategy(RenderStrategy):
    graph_builder = ClassicGraphBuilder()

    def input_files(self, plan: RenderPlan) -> list[str]:
        return [seg.file_path for seg in plan.segments]


class StemMultiDeckStrategy(RenderStrategy):
    graph_builder = StemGraphBuilder()

    def input_files(self, plan: RenderPlan) -> list[str]:
        assert plan.stem_segments is not None
        return [seg.stem_paths[stem] for seg in plan.stem_segments for stem in STEM_ORDER]


def select_strategy(plan: RenderPlan) -> RenderStrategy:
    """Pick the render strategy via the plan's explicit mode.

    Transitional back-compat: legacy plans built via ``build_stem_render_plan``
    still default to ``mode=CLASSIC`` but carry ``stem_segments`` — dispatch them
    to the stem strategy until Task 9 rebuilds the planner to set the mode.
    """
    if plan.mode is RenderMode.CLASSIC and plan.stem_segments is not None:
        return StemMultiDeckStrategy()
    return {
        RenderMode.CLASSIC: ClassicEqStrategy(),
        RenderMode.STEM: StemMultiDeckStrategy(),
    }[plan.mode]
