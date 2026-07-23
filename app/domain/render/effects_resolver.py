"""Resolve render-plan effect preset names into value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ResolvedEcho:
    delay_ms: float
    decay: float
    taps: int
    wet_dry_ratio: float

    def ffmpeg_aecho_expr(self) -> str:
        in_gain = 1.0 - self.wet_dry_ratio * 0.3
        out_gain = min(1.5, self.wet_dry_ratio * 1.2)
        delays = [self.delay_ms * (i + 1) for i in range(self.taps)]
        decays = [self.decay ** (i + 1) for i in range(self.taps)]
        delay_str = "|".join(f"{d:.0f}" for d in delays)
        decay_str = "|".join(f"{d:.3f}" for d in decays)
        return f"{in_gain:.3f}:{out_gain:.3f}:{delay_str}:{decay_str}"


@dataclass(frozen=True, slots=True)
class ResolvedReverb:
    decay_s: float
    pre_delay_ms: float
    highpass_hz: int
    lowpass_hz: int

    def ffmpeg_chain(self) -> str:
        spacing = max(45.0, self.decay_s * 45.0)
        delays = [self.pre_delay_ms + spacing * i for i in range(3)]
        decay = max(0.20, min(0.72, self.decay_s / 7.0))
        decays = [decay ** (i + 1) for i in range(3)]
        delay_str = "|".join(f"{d:.0f}" for d in delays)
        decay_str = "|".join(f"{d:.3f}" for d in decays)
        return (
            f"aecho=0.800:0.900:{delay_str}:{decay_str},"
            f"highpass=f={self.highpass_hz},lowpass=f={self.lowpass_hz}"
        )


@dataclass(frozen=True, slots=True)
class ResolvedSweepPlan:
    start_freq_hz: float
    end_freq_hz: float


@dataclass(frozen=True, slots=True)
class ResolvedSweep:
    outgoing: ResolvedSweepPlan | None = None
    incoming: ResolvedSweepPlan | None = None
    resonance: float = 0.7


@dataclass(frozen=True, slots=True)
class ResolvedEffects:
    echo: ResolvedEcho | None = None
    sweep: ResolvedSweep | None = None
    reverb: ResolvedReverb | None = None


ECHO_PRESETS: dict[str, ResolvedEcho] = {
    "techno_standard": ResolvedEcho(delay_ms=375, decay=0.4, taps=3, wet_dry_ratio=0.45),
    "vocal_throw": ResolvedEcho(delay_ms=500, decay=0.35, taps=4, wet_dry_ratio=0.55),
    "industrial_stutter": ResolvedEcho(delay_ms=94, decay=0.4, taps=3, wet_dry_ratio=0.3),
    "dub_space": ResolvedEcho(delay_ms=750, decay=0.6, taps=4, wet_dry_ratio=0.5),
    "acid_bounce": ResolvedEcho(delay_ms=188, decay=0.5, taps=3, wet_dry_ratio=0.4),
}

FILTER_PRESETS: dict[str, ResolvedSweep] = {
    "classic_lowpass": ResolvedSweep(
        outgoing=ResolvedSweepPlan(start_freq_hz=14000, end_freq_hz=200),
        incoming=ResolvedSweepPlan(start_freq_hz=200, end_freq_hz=14000),
        resonance=0.5,
    ),
    "acid_squelch": ResolvedSweep(
        outgoing=ResolvedSweepPlan(start_freq_hz=8000, end_freq_hz=800),
        incoming=ResolvedSweepPlan(start_freq_hz=800, end_freq_hz=8000),
        resonance=1.0,
    ),
    "industrial_cut": ResolvedSweep(
        outgoing=ResolvedSweepPlan(start_freq_hz=20000, end_freq_hz=80),
        resonance=2.0,
    ),
    "hypnotic_wash": ResolvedSweep(
        outgoing=ResolvedSweepPlan(start_freq_hz=12000, end_freq_hz=300),
        incoming=ResolvedSweepPlan(start_freq_hz=300, end_freq_hz=12000),
        resonance=0.5,
    ),
    "dub_echo_sweep": ResolvedSweep(
        outgoing=ResolvedSweepPlan(start_freq_hz=10000, end_freq_hz=500),
        incoming=ResolvedSweepPlan(start_freq_hz=500, end_freq_hz=10000),
        resonance=0.8,
    ),
}

REVERB_PRESETS: dict[str, ResolvedReverb] = {
    "techno_hall": ResolvedReverb(
        decay_s=2.5,
        pre_delay_ms=25,
        highpass_hz=100,
        lowpass_hz=6000,
    ),
    "techno_cathedral": ResolvedReverb(
        decay_s=5.0,
        pre_delay_ms=40,
        highpass_hz=80,
        lowpass_hz=4000,
    ),
    "industrial_warehouse": ResolvedReverb(
        decay_s=3.0,
        pre_delay_ms=15,
        highpass_hz=120,
        lowpass_hz=10000,
    ),
    "dub_plate": ResolvedReverb(
        decay_s=1.8,
        pre_delay_ms=10,
        highpass_hz=200,
        lowpass_hz=5000,
    ),
    "minimal_room": ResolvedReverb(
        decay_s=1.0,
        pre_delay_ms=12,
        highpass_hz=150,
        lowpass_hz=8000,
    ),
}


class EffectPresetResolver:
    def resolve(self, plan: Any) -> ResolvedEffects:
        return ResolvedEffects(
            echo=self._resolve_echo(getattr(plan, "echo_preset", None)),
            sweep=self._resolve_sweep(getattr(plan, "filter_sweep_preset", None)),
            reverb=self._resolve_reverb(getattr(plan, "reverb_preset", None)),
        )

    @staticmethod
    def _resolve_echo(name: str | None) -> ResolvedEcho | None:
        if name is None:
            return None
        return ECHO_PRESETS.get(name)

    @staticmethod
    def _resolve_sweep(name: str | None) -> ResolvedSweep | None:
        if name is None:
            return None
        return FILTER_PRESETS.get(name)

    @staticmethod
    def _resolve_reverb(name: str | None) -> ResolvedReverb | None:
        if name is None:
            return None
        return REVERB_PRESETS.get(name)
