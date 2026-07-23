"""ReverbIR — room/hall/cathedral reverb via scipy convolution.

Techno DJs need reverb for:
- Atmospheric breakdowns (cathedral, decay 4-6s)
- Transition washes (hall, decay 2-3s)
- Industrial spaces (warehouse, early reflections dominant)
- Dub echoes (plate, bright, decay 1-2s)

Implementation: Schroeder reverberator (4 comb filters + 2 allpass filters)
generating an impulse response, then convolve with the source audio via
scipy.signal.fftconvolve (fast FFT-based convolution). No ffmpeg needed —
pure scipy FFT convolution with wet/dry mix.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import cast

import numpy as np


class ReverbSpace(Enum):
    ROOM = "room"
    HALL = "hall"
    CATHEDRAL = "cathedral"
    WAREHOUSE = "warehouse"
    PLATE = "plate"
    SPRING = "spring"


@dataclass
class ReverbIR:
    """Schroeder reverberator impulse response generator.

    decay_s: RT60 time (seconds for signal to drop 60 dB).
    pre_delay_ms: time before first reflection (room size perception).
    early_reflections: number of early reflections before diffuse tail.
    modulation_hz: subtle pitch modulation for lush sound (0 = off).
    mix_ratio: 0.0 = dry, 1.0 = all wet.
    highpass_hz: cut rumble from reverb tail.
    lowpass_hz: darken the tail (muffled = smaller space feel).
    """

    decay_s: float = 2.5
    pre_delay_ms: float = 20.0
    early_reflections: int = 8
    modulation_hz: float = 0.0
    mix_ratio: float = 0.35
    highpass_hz: float = 80.0
    lowpass_hz: float = 8000.0
    sample_rate: int = 44100
    space: ReverbSpace = ReverbSpace.HALL

    @property
    def total_samples(self) -> int:
        """IR length: decay time + pre-delay + safety margin."""
        return int(self.sample_rate * (self.decay_s + self.pre_delay_ms / 1000.0 + 0.5))

    def generate_ir(self) -> np.ndarray:
        """Generate the impulse response via Schroeder algorithm.

        Returns a mono float32 numpy array of the IR.
        """
        sr = self.sample_rate
        total = self.total_samples
        ir = np.zeros(total, dtype=np.float32)

        # ── Initial impulse ──
        ir[0] = 1.0

        # ── Comb filters ──
        # Four parallel comb filters with prime-number delay lengths
        # for dense, non-periodic decay
        comb_delays_ms = [29.7, 37.1, 41.3, 43.7]
        comb_gains = [10 ** (-3 * d / (self.decay_s * 1000)) for d in comb_delays_ms]

        for delay_ms, gain in zip(comb_delays_ms, comb_gains, strict=False):
            delay_samples = int(sr * delay_ms / 1000.0)
            for n in range(delay_samples, total):
                ir[n] += gain * ir[n - delay_samples] if n >= delay_samples else 0

        # ── Allpass filters (diffusion) ──
        ap_delays_ms = [5.1, 1.7]
        ap_gains = [0.7, 0.7]

        for delay_ms, ap_gain in zip(ap_delays_ms, ap_gains, strict=False):
            delay_samples = int(sr * delay_ms / 1000.0)
            temp = ir.copy()
            for n in range(total):
                delayed = temp[n - delay_samples] if n >= delay_samples else 0.0
                ir[n] = -ap_gain * ir[n] + delayed + ap_gain * temp[n]

        # ── Pre-delay ──
        pre_samples = int(sr * self.pre_delay_ms / 1000.0)
        if pre_samples > 0:
            ir = np.concatenate([np.zeros(pre_samples, dtype=np.float32), ir[:-pre_samples]])

        # ── Normalize ──
        peak = np.max(np.abs(ir))
        if peak > 1e-10:
            ir = ir / peak * 0.95

        # ── Decay envelope (exponential) ──
        decay_start = pre_samples
        decay_len = total - decay_start
        if decay_len > 0:
            envelope = np.exp(-3.0 * np.arange(decay_len) / (self.decay_s * sr))
            ir[decay_start:] *= envelope.astype(np.float32)

        return ir.astype(np.float32)

    def apply(self, audio: np.ndarray) -> np.ndarray:
        """Apply reverb to mono/stereo audio via FFT convolution.

        audio: (samples,) or (samples, channels) float32 array.
        Returns convolved audio with wet/dry mix.
        """
        from scipy.signal import fftconvolve

        ir = self.generate_ir()

        if audio.ndim == 1:
            wet = fftconvolve(audio, ir, mode="full")[: len(audio)]
            return cast(
                np.ndarray,
                (1.0 - self.mix_ratio) * audio + self.mix_ratio * wet.astype(np.float32),
            )

        # Stereo: apply same IR to both channels
        result = np.zeros_like(audio)
        for ch in range(audio.shape[1]):
            wet = fftconvolve(audio[:, ch], ir, mode="full")[: audio.shape[0]]
            result[:, ch] = (1.0 - self.mix_ratio) * audio[:, ch] + self.mix_ratio * wet.astype(
                np.float32
            )
        return result

    def apply_mono(self, audio: np.ndarray) -> np.ndarray:
        """Apply reverb to mono audio, returning mono."""
        from scipy.signal import fftconvolve

        ir = self.generate_ir()
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        wet = fftconvolve(audio, ir, mode="full")[: len(audio)]
        return cast(
            np.ndarray,
            (1.0 - self.mix_ratio) * audio + self.mix_ratio * wet.astype(np.float32),
        )


# ── Preset library ──────────────────────────────────────────

TECHNO_HALL = ReverbIR(
    decay_s=2.5,
    pre_delay_ms=25,
    early_reflections=8,
    mix_ratio=0.30,
    highpass_hz=100,
    lowpass_hz=6000,
    space=ReverbSpace.HALL,
)

TECHNO_CATHEDRAL = ReverbIR(
    decay_s=5.0,
    pre_delay_ms=40,
    early_reflections=12,
    mix_ratio=0.25,
    highpass_hz=80,
    lowpass_hz=4000,
    space=ReverbSpace.CATHEDRAL,
)

INDUSTRIAL_WAREHOUSE = ReverbIR(
    decay_s=3.0,
    pre_delay_ms=15,
    early_reflections=6,
    mix_ratio=0.40,
    highpass_hz=120,
    lowpass_hz=10000,
    space=ReverbSpace.WAREHOUSE,
)

DUB_PLATE = ReverbIR(
    decay_s=1.8,
    pre_delay_ms=10,
    early_reflections=4,
    mix_ratio=0.50,
    highpass_hz=200,
    lowpass_hz=5000,
    space=ReverbSpace.PLATE,
)

MINIMAL_ROOM = ReverbIR(
    decay_s=1.0,
    pre_delay_ms=12,
    early_reflections=5,
    mix_ratio=0.20,
    highpass_hz=150,
    lowpass_hz=8000,
    space=ReverbSpace.ROOM,
)

REVERB_PRESETS: dict[str, ReverbIR] = {
    "techno_hall": TECHNO_HALL,
    "techno_cathedral": TECHNO_CATHEDRAL,
    "industrial_warehouse": INDUSTRIAL_WAREHOUSE,
    "dub_plate": DUB_PLATE,
    "minimal_room": MINIMAL_ROOM,
}
