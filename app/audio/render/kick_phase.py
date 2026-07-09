"""Kick-grid detection for the render engine (ported from analyze()).

Low-pass to ~150 Hz to isolate the kick, run librosa onset+beat tracking on
that band, take the first detected kick as the phase anchor. We anchor on the
KICK (not any onset) because a melodic pickup before the downbeat would make
the beats not line up.
"""

from __future__ import annotations

_LP_HZ = 150
_SR = 22050


def compute_kick_phase(file_path: str, bpm: float) -> tuple[float, float]:
    """Return (trim_start_s, phase_ms) for the first detected kick.

    Wraps ``detect_kick_trim`` to expose the render-friendly interface
    consumed by ``beatgrid_builder``.
    """
    trim_s = detect_kick_trim(file_path, start_s=0.0, bpm=bpm)
    return trim_s, round(trim_s * 1000.0, 2)


def detect_kick_trim(file_path: str, *, start_s: float, bpm: float) -> float:
    """Return the render trim (seconds into the FILE) where the first kick lands.

    ``start_s`` is the track's mix-in offset; the returned value is
    ``start_s + first_kick_offset`` so ``render`` starts exactly on a kick.
    """
    import librosa
    import numpy as np
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
