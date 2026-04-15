"""Tests for fitness functions — focused on realistic techno LUFS ranges."""

from app.entities.audio.features import TrackFeatures
from app.optimization.fitness import energy_arc_score


def _order(n: int) -> tuple[list[TrackFeatures], list[int], dict[int, int]]:
    track_ids = list(range(n))
    idx_map = {tid: tid for tid in track_ids}
    return track_ids, idx_map


def test_energy_arc_perfect_techno_arc():
    """Tracks following a realistic techno arc (-13 -> -10 -> -11 LUFS) score high."""
    n = 10
    track_ids, idx_map = _order(n)
    # Simulate a proper techno energy arc: quiet start -> loud peak -> slight cool-down
    lufs_values = [-13.5, -13.0, -12.5, -12.0, -11.5, -11.0, -10.5, -10.0, -10.5, -11.0]
    tracks = [TrackFeatures(integrated_lufs=v) for v in lufs_values]
    score = energy_arc_score(tracks, track_ids, idx_map)
    assert score >= 0.70, f"Perfect techno arc should score >= 0.70, got {score:.3f}"


def test_energy_arc_flat_techno_scores_reasonably():
    """All tracks at -12 LUFS (flat mix) should score above 0.50."""
    n = 10
    track_ids, idx_map = _order(n)
    tracks = [TrackFeatures(integrated_lufs=-12.0) for _ in range(n)]
    score = energy_arc_score(tracks, track_ids, idx_map)
    assert score >= 0.50, f"Flat -12 LUFS mix should score >= 0.50, got {score:.3f}"


def test_energy_arc_rejects_unrealistic_start():
    """A track at -22 LUFS (near-silence) at position 0 should NOT be the ideal start."""
    n = 5
    track_ids, idx_map = _order(n)
    # One realistic track at -12 vs one near-silent at -22
    tracks_realistic = [TrackFeatures(integrated_lufs=-12.0) for _ in range(n)]
    tracks_silent = [TrackFeatures(integrated_lufs=-22.0)] + [
        TrackFeatures(integrated_lufs=-12.0) for _ in range(n - 1)
    ]
    score_realistic = energy_arc_score(tracks_realistic, track_ids, idx_map)
    score_silent = energy_arc_score(tracks_silent, track_ids, idx_map)
    # Realistic first track should score better than silent first track
    assert score_realistic > score_silent, (
        f"Realistic first track ({score_realistic:.3f}) should beat "
        f"silent first track ({score_silent:.3f})"
    )


def test_energy_arc_techno_range_beats_extreme_range():
    """Tracks in -10 to -14 LUFS range should outperform tracks going to -22 LUFS."""
    n = 10
    track_ids, idx_map = _order(n)
    # Techno-realistic: -13 to -10 range
    tracks_techno = [TrackFeatures(integrated_lufs=-13.0 + i * 0.33) for i in range(n)]
    # Extreme range: -22 to -6 (old formula's ideal)
    lufs_extreme = [-22.0, -19.0, -16.0, -13.0, -10.0, -8.0, -7.0, -6.0, -8.0, -10.0]
    tracks_extreme = [TrackFeatures(integrated_lufs=v) for v in lufs_extreme]

    score_techno = energy_arc_score(tracks_techno, track_ids, idx_map)
    score_extreme = energy_arc_score(tracks_extreme, track_ids, idx_map)

    assert score_techno >= score_extreme, (
        f"Techno range ({score_techno:.3f}) should score >= extreme range ({score_extreme:.3f})"
    )
