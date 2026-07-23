"""FilterSweepPlan — automated filter sweeps for DJ transitions.

Generates ffmpeg filter graph fragments for:
- Low-pass sweep (closing filter → tension builds → drop)
- High-pass sweep (opening filter → energy release)
- Band-pass sweep (isolation → focus)
- Notch sweep (phase effect for acid/industrial)

The sweep is applied during the transition window between two tracks:
  outgoing track → filter closes (lowpass sweep down)
  incoming track → filter opens (highpass sweep up)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class SweepDirection(Enum):
    CLOSE = "close"  # lowpass: freq goes down
    OPEN = "open"  # highpass: freq goes up
    PEAK = "peak"  # bandpass: freq sweeps through middle


class SweepCurve(Enum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"  # faster at start, slows down (natural feel)
    LOGARITHMIC = "logarithmic"  # slow start, speeds up (tension release)


@dataclass(frozen=True, slots=True)
class FilterSweepPlan:
    """One filter sweep applied during a transition window.

    start_freq_hz / end_freq_hz: sweep range (20-20000 Hz).
    curve: LINEAR for clinical techno, EXPONENTIAL for organic feel.
    resonance: Q factor (0.5 = gentle, 2.0 = squelchy acid).
    apply_to: 'outgoing' (close filter on current track), 'incoming' (open filter
        on next track), or 'both'.
    """

    start_freq_hz: float
    end_freq_hz: float
    direction: SweepDirection = SweepDirection.CLOSE
    curve: SweepCurve = SweepCurve.EXPONENTIAL
    resonance: float = 0.7
    apply_to: str = "outgoing"
    start_beat: float = 0.0  # beat offset within transition window

    def frequency_at(self, t: float, total_duration: float) -> float:
        """Compute filter frequency at normalized time t (0..1)."""
        if total_duration <= 0:
            return self.end_freq_hz
        ratio = max(0.0, min(1.0, t / total_duration))

        if self.curve == SweepCurve.LINEAR:
            interp = ratio
        elif self.curve == SweepCurve.EXPONENTIAL:
            interp = (math.exp(ratio * 3.0) - 1.0) / (math.exp(3.0) - 1.0)
        else:  # logarithmic
            interp = math.log(1.0 + ratio * 9.0) / math.log(10.0)

        return self.start_freq_hz + (self.end_freq_hz - self.start_freq_hz) * interp

    def ffmpeg_lowpass_expr(self, total_duration_s: float) -> str:
        """Generate ffmpeg lowpass filter expression for timeline-based automation.

        Uses the ``lowpass`` filter with a time-varying frequency via the
        ``t`` (timeline) parameter in the filter expression.
        """
        start = self.start_freq_hz
        end = self.end_freq_hz
        dur = total_duration_s

        if self.curve == SweepCurve.LINEAR:
            expr = f"lowpass=f='{start}+({end}-{start})*t/{dur}':p=1"
        elif self.curve == SweepCurve.EXPONENTIAL:
            expr = f"lowpass=f='{start}+({end}-{start})*(exp(3*t/{dur})-1)/(exp(3)-1)':p=1"
        else:
            expr = f"lowpass=f='{start}+({end}-{start})*log(1+9*t/{dur})/log(10)':p=1"
        return expr

    def ffmpeg_highpass_expr(self, total_duration_s: float) -> str:
        """Generate ffmpeg highpass filter expression."""
        start = self.start_freq_hz
        end = self.end_freq_hz
        dur = total_duration_s

        if self.curve == SweepCurve.LINEAR:
            expr = f"highpass=f='{start}+({end}-{start})*t/{dur}':p=1"
        elif self.curve == SweepCurve.EXPONENTIAL:
            expr = f"highpass=f='{start}+({end}-{start})*(exp(3*t/{dur})-1)/(exp(3)-1)':p=1"
        else:
            expr = f"highpass=f='{start}+({end}-{start})*log(1+9*t/{dur})/log(10)':p=1"
        return expr


# ── Preset factory ──────────────────────────────────────────


@dataclass
class TransitionFilterPreset:
    """Pair of sweeps for a complete transition: one on outgoing, one on incoming."""

    outgoing: FilterSweepPlan | None = None
    incoming: FilterSweepPlan | None = None
    resonance: float = 0.7


# Pre-built presets for common transition types
CLASSIC_LOWPASS = TransitionFilterPreset(
    outgoing=FilterSweepPlan(
        start_freq_hz=14000,
        end_freq_hz=200,
        direction=SweepDirection.CLOSE,
        curve=SweepCurve.EXPONENTIAL,
        resonance=0.5,
    ),
    incoming=FilterSweepPlan(
        start_freq_hz=200,
        end_freq_hz=14000,
        direction=SweepDirection.OPEN,
        curve=SweepCurve.LOGARITHMIC,
        resonance=0.5,
        apply_to="incoming",
    ),
    resonance=0.5,
)

ACID_SQUELCH = TransitionFilterPreset(
    outgoing=FilterSweepPlan(
        start_freq_hz=8000,
        end_freq_hz=800,
        direction=SweepDirection.CLOSE,
        curve=SweepCurve.LINEAR,
        resonance=1.0,
    ),
    incoming=FilterSweepPlan(
        start_freq_hz=800,
        end_freq_hz=8000,
        direction=SweepDirection.OPEN,
        curve=SweepCurve.LINEAR,
        resonance=1.0,
        apply_to="incoming",
    ),
    resonance=1.0,
)

INDUSTRIAL_CUT = TransitionFilterPreset(
    outgoing=FilterSweepPlan(
        start_freq_hz=20000,
        end_freq_hz=80,
        direction=SweepDirection.CLOSE,
        curve=SweepCurve.EXPONENTIAL,
        resonance=2.0,
    ),
    incoming=None,  # incoming drops in hard
    resonance=2.0,
)

HYPNOTIC_WASH = TransitionFilterPreset(
    outgoing=FilterSweepPlan(
        start_freq_hz=12000,
        end_freq_hz=300,
        direction=SweepDirection.CLOSE,
        curve=SweepCurve.LOGARITHMIC,
        resonance=0.5,
    ),
    incoming=FilterSweepPlan(
        start_freq_hz=300,
        end_freq_hz=12000,
        direction=SweepDirection.OPEN,
        curve=SweepCurve.LOGARITHMIC,
        resonance=0.3,
        apply_to="incoming",
    ),
    resonance=0.5,
)

DUB_ECHO_SWEEP = TransitionFilterPreset(
    outgoing=FilterSweepPlan(
        start_freq_hz=10000,
        end_freq_hz=500,
        direction=SweepDirection.CLOSE,
        curve=SweepCurve.EXPONENTIAL,
        resonance=0.8,
    ),
    incoming=FilterSweepPlan(
        start_freq_hz=500,
        end_freq_hz=10000,
        direction=SweepDirection.OPEN,
        curve=SweepCurve.LOGARITHMIC,
        resonance=0.4,
        apply_to="incoming",
    ),
    resonance=0.8,
)

FILTER_PRESETS: dict[str, TransitionFilterPreset] = {
    "classic_lowpass": CLASSIC_LOWPASS,
    "acid_squelch": ACID_SQUELCH,
    "industrial_cut": INDUSTRIAL_CUT,
    "hypnotic_wash": HYPNOTIC_WASH,
    "dub_echo_sweep": DUB_ECHO_SWEEP,
}
