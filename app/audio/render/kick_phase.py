"""Kick-grid detection for the render engine.

Low-pass to ~150 Hz to isolate the kick, peak-pick the transient envelope, then
derive the grid from the MEASURED kick intervals (robust median) and anchor on
the first on-grid kick. We anchor on the KICK (not any onset) because a melodic
pickup before the downbeat would make the beats not line up.

The detection window is long (~100 s) so tracks with long intros still expose
their real kick pattern — a short window only sees intro percussion and yields
a garbage BPM (e.g. Dune's first real kick lands at ~40 s).
"""

from __future__ import annotations

import numpy as np

_LP_HZ = 150
_SR = 22050
_DETECT_WINDOW_S = 100.0
_THRESHOLD_RATIO = 0.12
_PEAK_PRE = 0.15
_PEAK_POST = 0.15
_PEAK_PRE_AVG = 0.2
_PEAK_POST_AVG = 0.5
_PEAK_DELTA = 0.03
_PEAK_WAIT = 0.2
_MIN_KICKS = 10
_ONGRID_BEAT_RATIO = 0.25


def compute_kick_phase(file_path: str, bpm: float) -> tuple[float, float]:
    """Return (trim_start_s, phase_ms) for the first on-grid kick.

    Wraps ``detect_kick_trim`` to expose the render-friendly interface
    consumed by ``beatgrid_builder``.
    """
    trim_s, _bpm = detect_kick_trim(file_path, start_s=0.0, bpm=bpm)
    return trim_s, round(trim_s * 1000.0, 2)


def detect_kick_trim(file_path: str, *, start_s: float, bpm: float) -> tuple[float, float]:
    """Return (render_trim_s, bpm_measured) for the first on-grid kick.

    ``start_s`` is the track's mix-in offset; the returned trim is
    ``start_s + first_kick_offset`` so ``render`` starts exactly on a kick.
    """
    import librosa
    from scipy.signal import butter, sosfiltfilt

    sos = butter(4, _LP_HZ, btype="low", fs=_SR, output="sos")
    y, _ = librosa.load(file_path, sr=_SR, offset=start_s, duration=_DETECT_WINDOW_S, mono=True)
    if y.size == 0:
        return round(start_s, 4), bpm
    low = sosfiltfilt(sos, y).astype(np.float32)
    env = _envelope(low)

    peak_times = _peak_times(env)
    thresh = _THRESHOLD_RATIO * float(np.max(env))
    kicks = [start_s + t for t in peak_times if env[int(t * _SR)] > thresh]

    if len(kicks) < _MIN_KICKS:
        return _fallback_trim(file_path, start_s=start_s, bpm=bpm), bpm

    diffs = np.diff(np.asarray(kicks, dtype=float))
    med = float(np.median(diffs))
    if med <= 0.0:
        return _fallback_trim(file_path, start_s=start_s, bpm=bpm), bpm
    beat_s = float(np.median(diffs[diffs < 1.3 * med]))
    bpm_measured = 60.0 / beat_s

    anchor = _first_ongrid_kick(kicks, beat_s)
    return round(anchor, 4), round(bpm_measured, 4)


def _envelope(low: np.ndarray) -> np.ndarray:
    env = np.abs(low)
    win = max(1, int(0.004 * _SR))
    return np.convolve(env, np.ones(win) / win, mode="same")


def _peak_times(env: np.ndarray) -> list[float]:
    import librosa

    idx = librosa.util.peak_pick(
        env,
        pre_max=int(_PEAK_PRE * _SR),
        post_max=int(_PEAK_POST * _SR),
        pre_avg=int(_PEAK_PRE_AVG * _SR),
        post_avg=int(_PEAK_POST_AVG * _SR),
        delta=_PEAK_DELTA,
        wait=int(_PEAK_WAIT * _SR),
    )
    return [float(i) / _SR for i in idx]


def _first_ongrid_kick(kicks: list[float], beat_s: float) -> float:
    k = np.asarray(kicks, dtype=float)
    phase = k % beat_s
    mu = np.angle(np.exp(2j * np.pi * phase / beat_s).sum()) * beat_s / (2 * np.pi)
    grid_phase = mu % beat_s
    dist = np.abs((k - grid_phase) % beat_s)
    dist = np.minimum(dist, beat_s - dist)
    ongrid = k[dist <= _ONGRID_BEAT_RATIO * beat_s]
    return float(ongrid[0]) if len(ongrid) else float(k[0])


def _fallback_trim(file_path: str, *, start_s: float, bpm: float) -> float:
    import librosa
    from scipy.signal import butter, sosfiltfilt

    sos = butter(4, _LP_HZ, btype="low", fs=_SR, output="sos")
    y, _ = librosa.load(file_path, sr=_SR, offset=start_s, duration=24.0, mono=True)
    low = sosfiltfilt(sos, y).astype(np.float32)
    env = librosa.onset.onset_strength(y=low, sr=_SR)
    _, beats = librosa.beat.beat_track(
        onset_envelope=env, sr=_SR, start_bpm=bpm, units="time", tightness=140
    )
    beats = np.asarray(beats, dtype=float)
    cand = beats[beats >= 0.03]
    first_kick = float(cand[0]) if len(cand) else 0.0
    return round(start_s + first_kick, 4)
