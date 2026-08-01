"""Sub-beat kick-phase refinement.

The kick anchor from ``detect_kick_trim`` already lands on a real kick; this
nudges it to the start of the kick transient for sub-beat precision. It works
on a tiny local window of the SOURCE file (no time-stretch), so it can never
jump half a beat the way the old ffmpeg+comb search did, and the shift is
capped at a quarter beat.
"""

from __future__ import annotations

_SR = 22050
_LOAD_MARGIN_S = 0.4
_LOAD_WINDOW_S = 0.8
_ONGRID_BEAT_RATIO = 0.25


def refine_phase(
    file_path: str, *, base_trim_s: float, bpm: float, target_bpm: float = 130.0
) -> tuple[float, float]:
    """Return (phase_delta_ms, refined_trim_s) for one track.

    ``base_trim_s`` is the raw kick anchor from ``detect_kick_trim``.
    """
    import librosa
    import numpy as np
    from scipy.signal import butter, sosfiltfilt

    beat_s = 60.0 / bpm
    win_lo = max(0.0, base_trim_s - _LOAD_MARGIN_S)
    y, _ = librosa.load(file_path, sr=_SR, mono=True, offset=win_lo, duration=_LOAD_WINDOW_S)
    if y.size == 0:
        return 0.0, round(base_trim_s, 4)

    sos = butter(4, 150, btype="low", fs=_SR, output="sos")
    low = sosfiltfilt(sos, y).astype(np.float32)
    env = np.abs(low)
    win = max(1, int(0.004 * _SR))
    env = np.convolve(env, np.ones(win) / win, mode="same")

    peak_i = int(np.argmax(env))
    thresh = 0.5 * env[peak_i]
    onset_i = peak_i
    for j in range(peak_i, 0, -1):
        if env[j] <= thresh:
            onset_i = j
            break
    onset_s = win_lo + onset_i / _SR
    delta = onset_s - base_trim_s
    if abs(delta) > _ONGRID_BEAT_RATIO * beat_s:
        delta = 0.0
    return round(delta * 1000.0, 1), round(base_trim_s + delta, 4)
