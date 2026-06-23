"""Regression: beats_loudness must share the beat analyzer's clip.

beats_loudness consumes the `beat` analyzer's beat_times, which are timestamps
within the 60s stitched clip. If beats_loudness runs on a different clip
(e.g. the full-track default), essentia gets beat positions that don't match
its samples and the feature comes back NULL for the whole library. Pin the
two clip durations together so they can't drift.
"""

from __future__ import annotations

from app.audio.analyzers.beat import BeatDetector
from app.audio.analyzers.beats_loudness import BeatsLoudnessAnalyzer


def test_beats_loudness_shares_beat_clip() -> None:
    assert BeatsLoudnessAnalyzer.clip_duration_s == BeatDetector.clip_duration_s


def test_beats_loudness_depends_on_beat() -> None:
    assert "beat" in BeatsLoudnessAnalyzer.depends_on
