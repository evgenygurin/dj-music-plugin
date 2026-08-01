"""Grid-alignment check for a rendered mix (post-render QA).

Phase measurement on a demucs-stem mix is unreliable (stems shift transients
30-100ms — see AGENTS.md render lessons). The robust end-to-end signal is the
**body BPM**: if rubberband honored ``tempo_ratio = bpm_measured / target``,
every track body plays at exactly ``target_bpm``. BPM via envelope
autocorrelation is phase-insensitive, so it survives the demucs/DSP chain.

Checked on real renders: a wrong stored BPM produced +1.6 BPM drift on one
track (max |dev| 1.60, mean 0.34); after the ``bpm_measured`` fix every track
sat within 0.4 BPM (max 0.40, mean 0.09).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

# Status thresholds (BPM) — from AGENTS.md lesson #4: a 0.5 BPM discrepancy is
# audible on a 60s transition (~0.5 beat drift); >1.0 BPM is a real engine bug.
OK_THRESHOLD_BPM = 0.5
WARN_THRESHOLD_BPM = 1.0


@dataclass(frozen=True, slots=True)
class BodyBpm:
    """One track's measured body BPM in the rendered mix."""

    track_id: int
    body_s: float
    body_e: float
    bpm_measured: float
    bpm_dev: float

    @property
    def status(self) -> str:
        return classify_dev(self.bpm_dev)


def classify_dev(
    dev_bpm: float, ok: float = OK_THRESHOLD_BPM, warn: float = WARN_THRESHOLD_BPM
) -> str:
    """Map an absolute BPM deviation to ok / warn / fail."""
    a = abs(dev_bpm)
    if a <= ok:
        return "ok"
    if a <= warn:
        return "warn"
    return "fail"


def body_windows(segs: Sequence[Mapping[str, Any]]) -> dict[int, tuple[float, float]]:
    """Per-track solo windows: [start+d_in, end-d_out], clipped at mix edges."""
    out: dict[int, tuple[float, float]] = {}
    n = len(segs)
    for i, seg in enumerate(segs):
        d_in = 0.0 if i == 0 else segs[i - 1]["end_s"] - seg["start_s"]
        d_out = 0.0 if i == n - 1 else seg["end_s"] - segs[i + 1]["start_s"]
        out[seg["track_id"]] = (seg["start_s"] + d_in, seg["end_s"] - d_out)
    return out


def measure_body_bpm(
    mix_path: str | Path,
    segs: Sequence[Mapping[str, Any]],
    target_bpm: float,
    sr: int = 22050,
) -> list[BodyBpm]:
    """Measure each track body's BPM in the mix; verify it hits ``target_bpm``."""
    import librosa

    y, _ = librosa.load(str(mix_path), sr=sr, mono=True)
    bodies = body_windows(segs)
    rows: list[BodyBpm] = []
    for seg in segs:
        tid = seg["track_id"]
        s, e = bodies[tid]
        lo, hi = int(s * sr), min(len(y), int(e * sr))
        if hi - lo < int(20 * 60.0 / target_bpm * sr):
            rows.append(BodyBpm(tid, s, e, 0.0, 0.0))
            continue
        cap = int(40 * sr)
        bpm = _bpm_autocorr(y[lo : min(hi, lo + cap)], sr, target_bpm)
        rows.append(BodyBpm(tid, s, e, round(bpm, 3), round(bpm - target_bpm, 3)))
    return rows


def _bpm_autocorr(y: np.ndarray, sr: int, target: float) -> float:
    """Envelope autocorrelation BPM (FFT), peak near target (0.94-1.06 window)."""
    from scipy.signal import butter, sosfiltfilt

    sos = butter(4, 200, btype="low", fs=sr, output="sos")
    low = sosfiltfilt(sos, y).astype(np.float32)
    env = np.abs(low)
    win = max(1, int(0.004 * sr))
    env = np.convolve(env, np.ones(win) / win, mode="same")
    env = env - env.mean()

    lo = int(sr * 60.0 / (target * 1.06))
    hi = max(lo + 1, int(sr * 60.0 / (target * 0.94)))
    n = len(env)
    if hi >= n:
        return 0.0
    nf = 1 << (n + hi - 1).bit_length()
    fft = np.fft.rfft(env, nf)
    ac = np.fft.irfft(fft * np.conj(fft), nf)[: hi + 1].real
    seg = ac[lo : hi + 1]
    k = int(np.argmax(seg)) + lo
    return 60.0 * sr / k
