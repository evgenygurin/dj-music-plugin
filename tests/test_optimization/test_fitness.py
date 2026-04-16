"""Tests for fitness functions — focused on realistic techno LUFS ranges."""

import pytest

from app.entities.audio.features import TrackFeatures
from app.optimization.fitness import bpm_smoothness, energy_arc_score, subgenre_variety


def _order(n: int) -> tuple[list[int], dict[int, int]]:
    track_ids = list(range(n))
    idx_map = {tid: tid for tid in track_ids}
    return track_ids, idx_map


# ── energy_arc_score ─────────────────────────────────────────────────────────


def test_energy_arc_perfect_techno_arc():
    """Tracks following a realistic techno arc (-13 -> -10 -> -11 LUFS) score high."""
    n = 10
    track_ids, idx_map = _order(n)
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
    """A track at -22 LUFS at position 0 should NOT be the ideal start."""
    n = 5
    track_ids, idx_map = _order(n)
    tracks_realistic = [TrackFeatures(integrated_lufs=-12.0) for _ in range(n)]
    tracks_silent = [TrackFeatures(integrated_lufs=-22.0)] + [
        TrackFeatures(integrated_lufs=-12.0) for _ in range(n - 1)
    ]
    score_realistic = energy_arc_score(tracks_realistic, track_ids, idx_map)
    score_silent = energy_arc_score(tracks_silent, track_ids, idx_map)
    assert score_realistic > score_silent, (
        f"Realistic first track ({score_realistic:.3f}) should beat "
        f"silent first track ({score_silent:.3f})"
    )


def test_energy_arc_techno_range_beats_extreme_range():
    """Tracks in -10 to -14 LUFS range should outperform tracks going to -22 LUFS."""
    n = 10
    track_ids, idx_map = _order(n)
    tracks_techno = [TrackFeatures(integrated_lufs=-13.0 + i * 0.33) for i in range(n)]
    lufs_extreme = [-22.0, -19.0, -16.0, -13.0, -10.0, -8.0, -7.0, -6.0, -8.0, -10.0]
    tracks_extreme = [TrackFeatures(integrated_lufs=v) for v in lufs_extreme]
    score_techno = energy_arc_score(tracks_techno, track_ids, idx_map)
    score_extreme = energy_arc_score(tracks_extreme, track_ids, idx_map)
    assert score_techno >= score_extreme, (
        f"Techno range ({score_techno:.3f}) should score >= extreme range ({score_extreme:.3f})"
    )


def test_energy_arc_correct_denominator_with_missing_lufs():
    """Tracks with LUFS=None should not dilute the score via wrong denominator."""
    n = 6
    track_ids, idx_map = _order(n)
    lufs_good = [-13.0, None, -12.0, None, -11.0, None]
    tracks_mixed = [TrackFeatures(integrated_lufs=v) for v in lufs_good]
    tracks_full = [TrackFeatures(integrated_lufs=-13.0 + i * 0.4) for i in range(n)]
    score_mixed = energy_arc_score(tracks_mixed, track_ids, idx_map)
    score_full = energy_arc_score(tracks_full, track_ids, idx_map)
    assert score_mixed >= score_full * 0.85, (
        f"Mixed LUFS ({score_mixed:.3f}) should be >= 85% of full ({score_full:.3f})"
    )


# ── bpm_smoothness ───────────────────────────────────────────────────────────


def test_bpm_smoothness_no_bpm_uses_spectral_not_flat():
    """When BPM=None, spectral centroid should be used instead of flat 0.5."""
    n = 4
    track_ids, idx_map = _order(n)
    tracks_similar = [TrackFeatures(bpm=None, spectral_centroid_hz=2000.0) for _ in range(n)]
    tracks_different = [
        TrackFeatures(bpm=None, spectral_centroid_hz=2000.0 + i * 3000.0) for i in range(n)
    ]
    score_similar = bpm_smoothness(tracks_similar, track_ids, idx_map)
    score_different = bpm_smoothness(tracks_different, track_ids, idx_map)
    assert score_similar > score_different, (
        f"Similar spectral ({score_similar:.3f}) should beat different ({score_different:.3f})"
    )
    assert score_similar != 0.5, "Should not return flat 0.5 when spectral data exists"


def test_bpm_smoothness_mixed_bpm_and_none_uses_best_available():
    """Mixed BPM/None pairs: computes from all available data."""
    n = 3
    track_ids, idx_map = _order(n)
    tracks = [
        TrackFeatures(bpm=130.0, spectral_centroid_hz=2000.0),
        TrackFeatures(bpm=None, spectral_centroid_hz=2100.0),
        TrackFeatures(bpm=131.0, spectral_centroid_hz=2050.0),
    ]
    score = bpm_smoothness(tracks, track_ids, idx_map)
    assert score > 0.5, f"Mixed data should produce > 0.5, got {score:.3f}"


# ── subgenre_variety ─────────────────────────────────────────────────────────


def test_subgenre_variety_reads_from_track_features_mood():
    """When moods dict is None, reads TrackFeatures.mood directly."""
    n = 4
    track_ids, idx_map = _order(n)
    moods_in_features = ["detroit", "minimal", "peak_time", "acid"]
    tracks = [TrackFeatures(mood=m) for m in moods_in_features]
    score = subgenre_variety(tracks, track_ids, idx_map, moods=None)
    assert score == 1.0, f"4 unique moods should give 1.0, got {score:.3f}"


def test_subgenre_variety_moods_dict_takes_priority():
    """External moods dict overrides TrackFeatures.mood."""
    n = 4
    track_ids, idx_map = _order(n)
    tracks = [TrackFeatures(mood="detroit") for _ in range(n)]
    moods_dict = {tid: "minimal" for tid in track_ids}
    score = subgenre_variety(tracks, track_ids, idx_map, moods=moods_dict)
    assert score == pytest.approx(0.25), f"1 unique mood should give 0.25, got {score:.3f}"


def test_subgenre_variety_no_mood_data_uses_energy_spread():
    """When no mood data anywhere, falls back to LUFS spread as diversity proxy."""
    n = 5
    track_ids, idx_map = _order(n)
    tracks_diverse = [TrackFeatures(mood=None, integrated_lufs=-10.0 + i * 1.5) for i in range(n)]
    tracks_flat = [TrackFeatures(mood=None, integrated_lufs=-12.0) for _ in range(n)]
    score_diverse = subgenre_variety(tracks_diverse, track_ids, idx_map, moods=None)
    score_flat = subgenre_variety(tracks_flat, track_ids, idx_map, moods=None)
    assert score_diverse > score_flat, (
        f"Diverse energy ({score_diverse:.3f}) should beat flat ({score_flat:.3f})"
    )
