"""Frame-level energy computation — extracted from energy.py and structure.py.

Pure functions, zero side effects, zero app/ dependencies.
Eliminates the duplicated frame energy loop in energy.py:44-54 and structure.py:71-81.
"""

from __future__ import annotations

import numpy as np


def compute_frame_energies(
    samples: np.ndarray,
    frame_length: int = 2048,
    hop_length: int = 512,
) -> np.ndarray:
    """Compute normalized short-time frame energies.

    Returns array of energies normalized to [0, 1] (max = 1.0).
    For empty/silent signals, returns array of zeros.
    """
    n_samples = len(samples)
    if n_samples == 0:
        return np.zeros(1, dtype=np.float64)

    n_frames = max(1, (n_samples - frame_length) // hop_length + 1)
    frame_energies = np.zeros(n_frames, dtype=np.float64)

    for i in range(n_frames):
        start = i * hop_length
        end = min(start + frame_length, n_samples)
        frame = samples[start:end]
        frame_energies[i] = float(np.mean(frame**2))

    max_energy = float(np.max(frame_energies))
    if max_energy > 0:
        frame_energies = frame_energies / max_energy

    return frame_energies


def compute_energy_slope(energies: np.ndarray) -> float:
    """Compute energy slope via linear regression.

    Returns slope coefficient. Positive = energy increasing over time.
    """
    n_frames = len(energies)
    if n_frames <= 1:
        return 0.0

    x = np.arange(n_frames, dtype=np.float64)
    slope, _ = np.polyfit(x, energies, 1)
    return float(slope)
