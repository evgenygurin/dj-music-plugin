"""ffmpeg ``filter_complex`` construction — Template Method + Strategy.

Two render algorithms share one skeleton:

* :class:`FilterGraphBuilder` (**Template Method**) — ``build`` walks the placed
  segments, delegates each per-segment block to a subclass, then appends the one
  shared master bus (amix → master EQ → limiter).
* :class:`ClassicGraphBuilder` — single file per track, asplit 3-band EQ
  bass-swap (highs phase 1, mids phase 2, bass pinpoint swap phase 3).
* :class:`StemGraphBuilder` — 4 demucs stems per track, staggered per-stem
  transitions with artifact-masking high-pass.
* :class:`RenderStrategy` (**Strategy**) — pairs a graph builder with its ffmpeg
  input expansion; :func:`select_strategy` picks the mode from the plan. The
  runner depends only on the strategy, so a new render mode is a new subclass —
  no edits to the runner or the handler (OCP).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.domain.render.eq import build_master_eq
from app.domain.render.models import (
    STEM_ORDER,
    RenderPlan,
    StemSegment,
    TrackSegment,
)

# Artifact-masking high-pass per stem (Hz) — removes demucs kick/bass bleed so
# the isolated bass stem owns the low end. None keeps the stem full-range.
_STEM_HPF_HZ: dict[str, int | None] = {
    "drums": None,
    "bass": None,
    "vocals": 120,
    "other": 80,
}


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

    def _segments(self, plan: RenderPlan) -> Sequence[TrackSegment]:
        return plan.segments

    def _segment_block(self, plan: RenderPlan, i: int, seg: object) -> tuple[list[str], str]:
        assert isinstance(seg, TrackSegment)
        xlo, xhi = plan.xsplit_low_hz, plan.xsplit_high_hz
        bar_s = 4.0 * (60.0 / plan.target_bpm)
        beat_s = 60.0 / plan.target_bpm
        low_x = plan.low_swap_beats * beat_s
        p1, p2 = plan.eq_phase_1_ratio, plan.eq_phase_2_ratio
        n = plan.n
        d_in, d_out, length = seg.d_in_s, seg.d_out_s, seg.length_s
        fd = min(plan.outro_fade_bars * bar_s, length)

        parts: list[str] = []
        base = (
            f"[{i}:a]atrim=start={seg.trim_start_s:.4f}:"
            f"duration={length / seg.tempo_ratio + 1.0:.3f},"
            f"asetpts=PTS-STARTPTS,rubberband=tempo={seg.tempo_ratio:.5f}:pitchq=quality,"
            f"atrim=duration={length:.3f},asetpts=PTS-STARTPTS,volume={seg.gain_db:.2f}dB,"
            f"aformat=sample_rates=44100:channel_layouts=stereo"
        )
        parts.append(f"{base}[s{i}]")
        parts.append(f"[s{i}]asplit=3[s{i}a][s{i}b][s{i}c]")
        parts.append(f"[s{i}a]lowpass=f={xlo}[lo{i}]")
        parts.append(f"[s{i}b]highpass=f={xlo},lowpass=f={xhi}[mid{i}]")
        parts.append(f"[s{i}c]highpass=f={xhi}[hi{i}]")

        # ── HIGH band: Phase 1 ──
        hi: list[str] = []
        if i > 0:
            hi.append(f"afade=t=in:curve=qsin:st=0:d={d_in * p1:.3f}")
        if i < n - 1:
            hi.append(f"afade=t=out:curve=qsin:st={length - d_out:.3f}:d={d_out * p1:.3f}")
        else:
            hi.append(f"afade=t=out:curve=qsin:st={length - fd:.3f}:d={fd:.3f}")
        parts.append(f"[hi{i}]{','.join(hi) if hi else 'acopy'}[H{i}]")

        # ── MID band: Phase 2 ──
        mid: list[str] = []
        if i > 0:
            mid.append(f"afade=t=in:curve=qsin:st={d_in * p1:.3f}:d={d_in * (p2 - p1):.3f}")
        if i < n - 1:
            mid.append(
                f"afade=t=out:curve=qsin:st={length - d_out * (1.0 - p1):.3f}:"
                f"d={d_out * (p2 - p1):.3f}"
            )
        else:
            mid.append(f"afade=t=out:curve=qsin:st={length - fd:.3f}:d={fd:.3f}")
        parts.append(f"[mid{i}]{','.join(mid) if mid else 'acopy'}[MID{i}]")

        # ── LOW band: pinpoint swap (Phase 3) ──
        lo: list[str] = []
        if i > 0:
            st = d_in * p2 - low_x / 2
            lo.append(f"afade=t=in:curve=qsin:st={st:.3f}:d={low_x:.3f}")
        if i < n - 1:
            st = length - d_out * (1.0 - p2) - low_x / 2
            lo.append(f"afade=t=out:curve=qsin:st={st:.3f}:d={low_x:.3f}")
        else:
            lo.append(f"afade=t=out:curve=qsin:st={length - fd:.3f}:d={fd:.3f}")
        parts.append(f"[lo{i}]{','.join(lo) if lo else 'acopy'}[Lo{i}]")

        t_ms = int(seg.start_s * 1000)
        parts.append(
            f"[H{i}][MID{i}][Lo{i}]amix=inputs=3:normalize=0,adelay={t_ms}|{t_ms}|{t_ms}[m{i}]"
        )
        return parts, f"[m{i}]"


class StemGraphBuilder(FilterGraphBuilder):
    """4-stem multi-deck: staggered per-stem transitions + bleed-masking HPF.

    Staggered like the classic 3-band ritual: OTHER swaps early (p1), DRUMS ride
    the whole window (continuous drive), VOCALS wide (p2), BASS a 1-beat pinpoint
    swap at ``bass_swap_ratio`` — only one bassline is ever at full. First track
    eases in, last fades out over ``outro_fade_bars``.
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
            parts.append(self._stem_chain(input_idx, seg, label, _STEM_HPF_HZ[stem]))
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
    def _stem_chain(input_idx: int, seg: StemSegment, label: str, hpf_hz: int | None) -> str:
        """One stem: trim → tempo-stretch → (optional HPF) → gain → format."""
        hpf = f"highpass=f={hpf_hz}," if hpf_hz else ""
        return (
            f"[{input_idx}:a]atrim=start={seg.trim_start_s:.4f}:"
            f"duration={seg.length_s / seg.tempo_ratio + 1.0:.3f},"
            f"asetpts=PTS-STARTPTS,rubberband=tempo={seg.tempo_ratio:.5f}:pitchq=quality,"
            f"atrim=duration={seg.length_s:.3f},asetpts=PTS-STARTPTS,"
            f"{hpf}"
            f"volume={seg.gain_db:.2f}dB,"
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
        elif stem == "other":
            fades.append(f"afade=t=in:curve=qsin:st=0:d={max(0.05, d_in * p1):.3f}")
        elif stem == "vocals":
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
        elif stem == "other":
            dur = max(0.05, d_out * p1)
            fades.append(f"afade=t=out:curve=qsin:st={length - dur:.3f}:d={dur:.3f}")
        elif stem == "vocals":
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
    """Pick the render strategy from the plan's mode (stem segments → stem)."""
    return StemMultiDeckStrategy() if plan.stem_segments else ClassicEqStrategy()
