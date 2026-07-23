"""AutomationCurve — parameter automation for ffmpeg filter graphs.

Generates time-varying parameter curves for:
- Volume rides (manual gain adjustments)
- EQ sweeps (parametric EQ automation)
- Pan automation (stereo movement)
- Send levels (reverb/delay dry/wet)

Curves are sampled at frame rate and converted to ffmpeg
timeline editing expressions or sendcmd/zmq commands.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np


class CurveType(Enum):
    LINEAR = "linear"
    S_CURVE = "s_curve"  # smooth start and end (cosine interpolation)
    EXPONENTIAL = "exponential"
    LOGARITHMIC = "logarithmic"
    STEP = "step"  # instant jump
    SAW = "saw"  # repeating ramp (LFO-like)
    TRIANGLE = "triangle"  # repeating up-down
    SINE = "sine"  # smooth sinusoidal LFO


class AutomatableParam(Enum):
    VOLUME = "volume"
    PAN = "pan"
    LOWPASS = "lowpass"
    HIGHPASS = "highpass"
    BANDPASS = "bandpass"
    REVERB_MIX = "reverb_mix"
    DELAY_MIX = "delay_mix"
    EQ_BAND_1 = "eq_band_1"
    EQ_BAND_2 = "eq_band_2"
    EQ_BAND_3 = "eq_band_3"


@dataclass
class AutomationPoint:
    """One keyframe in the automation curve."""

    time_s: float
    value: float
    curve_type: CurveType = CurveType.LINEAR


@dataclass
class AutomationCurve:
    """Complete automation curve for one parameter."""

    param: AutomatableParam
    points: list[AutomationPoint]  # sorted by time_s
    duration_s: float

    @classmethod
    def simple(
        cls,
        param: AutomatableParam,
        start_value: float,
        end_value: float,
        duration_s: float,
        curve_type: CurveType = CurveType.S_CURVE,
    ) -> AutomationCurve:
        """Create a simple start→end automation."""
        return cls(
            param=param,
            points=[
                AutomationPoint(time_s=0.0, value=start_value, curve_type=curve_type),
                AutomationPoint(time_s=duration_s, value=end_value),
            ],
            duration_s=duration_s,
        )

    @classmethod
    def lfo(
        cls,
        param: AutomatableParam,
        min_value: float,
        max_value: float,
        rate_hz: float,
        duration_s: float,
        shape: CurveType = CurveType.SINE,
    ) -> AutomationCurve:
        """Create an LFO-style repeating automation."""
        samples = max(2, int(duration_s * rate_hz * 4))
        t = np.linspace(0, duration_s, samples)
        if shape == CurveType.SAW:
            v = min_value + (max_value - min_value) * ((t * rate_hz) % 1.0)
        elif shape == CurveType.TRIANGLE:
            phase = (t * rate_hz) % 1.0
            v = min_value + (max_value - min_value) * (1.0 - abs(2.0 * phase - 1.0))
        else:  # sine
            v = min_value + (max_value - min_value) * 0.5 * (
                1.0 + np.sin(2 * math.pi * rate_hz * t)
            )
        points = [AutomationPoint(time_s=float(t[i]), value=float(v[i])) for i in range(samples)]
        return cls(param=param, points=points, duration_s=duration_s)

    def value_at(self, time_s: float) -> float:
        """Interpolate the curve value at a given time."""
        if not self.points:
            return 0.0
        if time_s <= self.points[0].time_s:
            return self.points[0].value
        if time_s >= self.points[-1].time_s:
            return self.points[-1].value

        # Find surrounding points
        for i in range(len(self.points) - 1):
            a = self.points[i]
            b = self.points[i + 1]
            if a.time_s <= time_s <= b.time_s:
                dt = b.time_s - a.time_s
                if dt < 1e-6:
                    return a.value
                t = (time_s - a.time_s) / dt
                return _interpolate(a.value, b.value, t, a.curve_type)
        return self.points[-1].value

    def sample(self, num_points: int) -> list[tuple[float, float]]:
        """Sample the curve at `num_points` evenly spaced positions."""
        t = np.linspace(0, self.duration_s, num_points)
        return [(float(ti), self.value_at(float(ti))) for ti in t]

    def to_ffmpeg_volume_expr(self, input_label: str = "0") -> str:
        """Generate ffmpeg volume filter expression."""
        if len(self.points) == 2 and self.duration_s > 0:
            a, b = self.points[0], self.points[1]
            return (
                f"[{input_label}:a]volume='{a.value}+({b.value}-{a.value})*"
                f"t/{self.duration_s}':eval=frame[out]"
            )
        # Multi-point: use piecewise
        return f"[{input_label}:a]volume=1.0[out]"


def _interpolate(a: float, b: float, t: float, curve: CurveType) -> float:
    if curve == CurveType.LINEAR:
        return a + (b - a) * t
    elif curve == CurveType.S_CURVE:
        smooth = (1.0 - math.cos(t * math.pi)) / 2.0
        return a + (b - a) * smooth
    elif curve == CurveType.EXPONENTIAL:
        exp_t = (math.exp(t * 3.0) - 1.0) / (math.exp(3.0) - 1.0)
        return a + (b - a) * exp_t
    elif curve == CurveType.LOGARITHMIC:
        log_t = math.log(1.0 + t * 9.0) / math.log(10.0)
        return a + (b - a) * log_t
    else:
        return b
