"""EchoPlan — delay throws for DJ transitions.

Implements the classic techno DJ technique: echo/delay applied to the last beat
or vocal phrase before a transition/drop.

ffmpeg `aecho` filter generates multi-tap delay with configurable
feedback (decay) and wet/dry mix.

Typical techno usage:
- Pre-drop echo: 3/16 or 1/4 note delay on last kick before breakdown
- Vocal throw: 1/2 note delay on last word before transition
- Industrial stutter: 1/16 note delay with high feedback for glitch effect
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DelayUnit(Enum):
    BEATS = "beats"
    MS = "ms"
    SIXTEENTH = "16th"
    EIGHTH = "8th"
    QUARTER = "4th"
    HALF = "2nd"
    WHOLE = "1bar"


def delay_unit_to_ms(unit: DelayUnit, bpm: float) -> float:
    """Convert a musical delay unit to milliseconds at the given BPM."""
    beat_ms = 60000.0 / bpm
    mapping = {
        DelayUnit.SIXTEENTH: beat_ms / 4,
        DelayUnit.EIGHTH: beat_ms / 2,
        DelayUnit.QUARTER: beat_ms,
        DelayUnit.HALF: beat_ms * 2,
        DelayUnit.WHOLE: beat_ms * 4,
    }
    return mapping.get(unit, beat_ms)


@dataclass(frozen=True, slots=True)
class EchoPlan:
    """A delay/echo configuration for a transition point.

    delay_ms: primary delay time in milliseconds (or use delay_unit+bpm).
    decay: feedback amount (0.0 = single echo, 0.7 = long tail, 0.95 = infinite).
    taps: number of echo taps (1 = simple delay, 4 = ping-pong feel).
    wet_dry_ratio: 0.0 = all dry, 1.0 = all wet. For DJ throws, usually 0.4-0.6.
    apply_on: 'incoming' (echo the new track entering) or 'outgoing' (echo the
        track leaving).
    pre_delay_beats: silence before first echo (for rhythmic placement).
    stereo_spread: 0.0 = mono, 1.0 = wide ping-pong.
    highpass_hz: cut lows from echo (keeps mix clean).
    lowpass_hz: cut highs from echo (dark, dubby feel).
    """

    delay_ms: float = 250.0
    delay_unit: DelayUnit | None = None
    bpm: float = 130.0
    decay: float = 0.5
    taps: int = 3
    wet_dry_ratio: float = 0.5
    apply_on: str = "outgoing"
    pre_delay_beats: float = 0.0
    stereo_spread: float = 0.5
    highpass_hz: float = 200.0
    lowpass_hz: float = 8000.0

    @property
    def effective_delay_ms(self) -> float:
        if self.delay_unit is not None:
            return delay_unit_to_ms(self.delay_unit, self.bpm)
        return self.delay_ms

    @property
    def pre_delay_ms(self) -> float:
        if self.bpm > 0:
            return self.pre_delay_beats * (60000.0 / self.bpm)
        return 0.0

    def ffmpeg_aecho_expr(self) -> str:
        """Build ffmpeg `aecho` filter arguments.

        Returns a string like: "0.8:0.6:250|500|750:0.5|0.25|0.125"
        (in_gain:out_gain:delays:decays)
        """
        in_gain = 1.0 - self.wet_dry_ratio * 0.3
        out_gain = self.wet_dry_ratio * 1.2
        out_gain = min(1.5, out_gain)

        # Build delay tap times (equally spaced by delay_ms)
        delays = [self.effective_delay_ms * (i + 1) for i in range(self.taps)]

        # Build per-tap decay (exponential falloff)
        decays = [self.decay ** (i + 1) for i in range(self.taps)]

        delay_str = "|".join(f"{d:.0f}" for d in delays)
        decay_str = "|".join(f"{d:.3f}" for d in decays)

        return f"{in_gain:.3f}:{out_gain:.3f}:{delay_str}:{decay_str}"

    def ffmpeg_filter_chain(self, input_label: str, output_label: str) -> str:
        """Full ffmpeg filter chain for echo processing.

        Applies: volume (pre-delay silence) → highpass → lowpass → aecho → mix.
        """
        aecho = self.ffmpeg_aecho_expr()
        chain = (
            f"[{input_label}]"
            f"adelay={self.pre_delay_ms:.0f}|{self.pre_delay_ms:.0f},"
            f"highpass=f={self.highpass_hz:.0f},"
            f"lowpass=f={self.lowpass_hz:.0f},"
            f"aecho={aecho}"
        )

        if self.stereo_spread > 0.01:
            width = 1.0 + self.stereo_spread * 2.0
            chain += f",stereowiden={width:.2f}"

        chain += f"[{output_label}]"
        return chain


# ── Preset library ──────────────────────────────────────────

TECHNO_STANDARD = EchoPlan(
    delay_ms=375,  # dotted 8th at 128 BPM
    decay=0.4,
    taps=3,
    wet_dry_ratio=0.45,
    highpass_hz=300,
    lowpass_hz=6000,
    stereo_spread=0.4,
)

VOCAL_THROW = EchoPlan(
    delay_ms=500,  # quarter note at 120 BPM
    decay=0.35,
    taps=4,
    wet_dry_ratio=0.55,
    highpass_hz=500,
    lowpass_hz=10000,
    stereo_spread=0.7,
    pre_delay_beats=1.0,  # one beat of silence before first echo
)

INDUSTRIAL_STUTTER = EchoPlan(
    delay_ms=94,  # 1/16 note at ~130 BPM
    decay=0.4,
    taps=3,
    wet_dry_ratio=0.3,
    highpass_hz=200,
    lowpass_hz=8000,
    stereo_spread=0.2,
)

DUB_SPACE = EchoPlan(
    delay_ms=750,  # half note feel
    decay=0.6,
    taps=4,
    wet_dry_ratio=0.5,
    highpass_hz=150,
    lowpass_hz=4000,
    stereo_spread=0.8,
)

ACID_BOUNCE = EchoPlan(
    delay_ms=188,  # 1/16 note triplet at ~128 BPM
    decay=0.5,
    taps=3,
    wet_dry_ratio=0.4,
    highpass_hz=400,
    lowpass_hz=8000,
    stereo_spread=0.6,
)

ECHO_PRESETS: dict[str, EchoPlan] = {
    "techno_standard": TECHNO_STANDARD,
    "vocal_throw": VOCAL_THROW,
    "industrial_stutter": INDUSTRIAL_STUTTER,
    "dub_space": DUB_SPACE,
    "acid_bounce": ACID_BOUNCE,
}
