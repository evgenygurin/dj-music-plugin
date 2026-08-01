import itertools

import numpy as np

from app.domain.performance.energy_arc import (
    ARC_PRESETS,
    ArcShape,
    TrackCandidate,
    fit_tracks_to_arc,
    peak_only_arc,
)


def test_peak_only_registered_in_presets():
    assert "peak_only" in ARC_PRESETS


def test_peak_only_arc_energy_peaks_near_75_percent():
    arc = peak_only_arc(num_tracks=8)
    slots = arc.build_slots()
    energies = [s.target_energy for s in slots]
    assert arc.shape is ArcShape.PEAK_ONLY
    peak_idx = int(np.argmax(energies))
    peak_pos = peak_idx / (len(energies) - 1)
    assert 0.6 <= peak_pos <= 0.9
    assert energies[0] < energies[peak_idx]
    assert energies[-1] < energies[peak_idx]
    assert all(0.45 <= e <= 0.80 for e in energies)
    assert all(a <= b for a, b in itertools.pairwise(energies[: peak_idx + 1]))
    assert all(a >= b for a, b in itertools.pairwise(energies[peak_idx:]))


def test_peak_only_flat_bpm():
    arc = peak_only_arc(num_tracks=6)
    slots = arc.build_slots()
    assert {s.target_bpm for s in slots} == {130.0}


def test_fit_tracks_to_arc_follows_peak_energy():
    energies = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
    candidates = [
        TrackCandidate(
            track_id=100 + i,
            bpm=130.0,
            energy_mean=e,
            key_code=None,
            integrated_lufs=-12.0,
            spectral_centroid_hz=0.0,
        )
        for i, e in enumerate(energies)
    ]
    arc = peak_only_arc(num_tracks=6)
    order = fit_tracks_to_arc(candidates, arc)
    assert order is not None
    ordered_energy = [energies[tid - 100] for tid in order]
    peak_idx = int(np.argmax(ordered_energy))
    peak_pos = peak_idx / (len(ordered_energy) - 1)
    assert 0.6 <= peak_pos <= 0.9
    assert ordered_energy[-1] < ordered_energy[peak_idx]
