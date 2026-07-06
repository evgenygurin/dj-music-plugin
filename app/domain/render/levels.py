"""Per-track loudness match: gain toward the median integrated LUFS.

Full-track integrated LUFS is far more reliable than a short-chunk RMS
(the script's note: measuring an intro chunk mis-fired). Clamp ±4 dB.
"""

from __future__ import annotations

from statistics import median

_CLAMP_DB = 4.0


def gains_to_median(lufs_by_track: dict[int, float | None]) -> dict[int, float]:
    """Return per-track gain (dB, clamped ±4) that moves each toward the median.

    Tracks with a missing (None) LUFS get 0.0 gain. The median is taken over
    the tracks that DO have a LUFS value.
    """
    known = [v for v in lufs_by_track.values() if v is not None]
    if not known:
        return {tid: 0.0 for tid in lufs_by_track}
    med = float(median(known))
    out: dict[int, float] = {}
    for tid, v in lufs_by_track.items():
        if v is None:
            out[tid] = 0.0
            continue
        out[tid] = round(max(-_CLAMP_DB, min(_CLAMP_DB, med - v)), 2)
    return out
