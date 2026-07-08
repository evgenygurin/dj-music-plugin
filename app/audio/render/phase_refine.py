"""Sub-beat kick-phase refinement (ported from qa()).

Stretch a 24 s chunk to the target BPM, take the kick onset envelope, and
cross-correlate it with an ideal target-BPM pulse comb to find the exact
sub-beat offset, so every track's kicks land on the SAME grid.
"""

from __future__ import annotations

import os
import subprocess
import tempfile

from app.audio.render._constants import HOP as _HOP
from app.audio.render._constants import SR as _SR


def refine_phase(
    file_path: str, *, base_trim_s: float, bpm: float, target_bpm: float = 130.0
) -> tuple[float, float]:
    """Return (phase_delta_ms, refined_trim_s) for one track.

    ``base_trim_s`` is the raw kick anchor from ``detect_kick_trim``.
    """
    import librosa
    import numpy as np
    from scipy.signal import butter, sosfiltfilt

    beat_s = 60.0 / target_bpm
    fpb = beat_s * _SR / _HOP  # onset-env frames per beat
    tempo = target_bpm / bpm
    sos = butter(4, 150, btype="low", fs=_SR, output="sos")

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{base_trim_s}",
            "-t",
            f"{24 * bpm / target_bpm + 1:.1f}",
            "-i",
            file_path,
            "-af",
            f"rubberband=tempo={tempo:.5f}",
            "-ar",
            str(_SR),
            "-ac",
            "1",
            tmp,
        ],
        stderr=subprocess.DEVNULL,
        check=False,
    )
    try:
        y, _ = librosa.load(tmp, sr=_SR, mono=True, duration=24.0)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    low = sosfiltfilt(sos, y).astype(np.float32)
    env = librosa.onset.onset_strength(y=low, sr=_SR, hop_length=_HOP)
    best_s, best_phi = -1.0, 0
    for phi in range(round(fpb)):
        idx = np.round(phi + np.arange(0, len(env) - 1, fpb)).astype(int)
        idx = idx[idx < len(env)]
        s = float(env[idx].sum())
        if s > best_s:
            best_s, best_phi = s, phi
    phase_s = best_phi * _HOP / _SR
    delta = phase_s if phase_s <= beat_s / 2 else phase_s - beat_s
    return round(delta * 1000.0, 1), round(base_trim_s + delta, 4)
