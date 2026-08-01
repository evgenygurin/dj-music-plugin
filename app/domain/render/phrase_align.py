"""Phrase-aligned track entry — snap an incoming trim to a phrase boundary.

Pure geometry: no I/O, no audio analysis. Keeps the kick grid intact by
only accepting near-whole-bar shifts (a bar is 4 beats; an integer number
of bars is a multiple of 4 beats, so every kick stays on the grid).
"""

from __future__ import annotations


def snap_trim_to_phrase(
    trim_s: float,
    phrase_boundaries_ms: list[int] | None,
    source_bpm: float,
    *,
    window_bars: int = 4,
) -> float:
    """Shift ``trim_s`` to the nearest phrase boundary when the move is safe.

    A shift is accepted only when it is (a) at most ``window_bars`` bars and
    (b) a near-whole number of bars (within 0.05 of an integer), which keeps
    the kick phase intact. Returns the adjusted trim (seconds), or the
    original when nothing qualifies.
    """
    if not phrase_boundaries_ms or source_bpm <= 0.0:
        return trim_s

    bar_ms = 4.0 * (60.0 / source_bpm) * 1000.0
    trim_ms = trim_s * 1000.0

    best_ms = min(phrase_boundaries_ms, key=lambda b: abs(b - trim_ms))
    delta_ms = best_ms - trim_ms
    if abs(delta_ms) > window_bars * bar_ms:
        return trim_s
    rem = abs(delta_ms) % bar_ms
    if min(rem, bar_ms - rem) > 0.05 * bar_ms:
        return trim_s
    return trim_s + delta_ms / 1000.0
