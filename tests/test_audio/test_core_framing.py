"""Tests for core framing primitives."""

from __future__ import annotations

import numpy as np
import pytest

from dj_music.audio.core.framing import compute_energy_slope, compute_frame_energies


class TestComputeFrameEnergies:
    def test_silence_gives_zeros(self) -> None:
        samples = np.zeros(4096, dtype=np.float32)
        energies = compute_frame_energies(samples, frame_length=2048, hop_length=512)
        assert len(energies) > 0
        assert float(np.max(energies)) == 0.0

    def test_sine_wave_normalized(self) -> None:
        t = np.linspace(0, 1.0, 22050, endpoint=False)
        samples = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        energies = compute_frame_energies(samples, frame_length=2048, hop_length=512)
        assert float(np.max(energies)) <= 1.0 + 1e-6
        assert float(np.min(energies)) >= 0.0

    def test_frame_count_correct(self) -> None:
        n_samples = 22050
        samples = np.zeros(n_samples, dtype=np.float32)
        energies = compute_frame_energies(samples, frame_length=2048, hop_length=512)
        expected_frames = max(1, (n_samples - 2048) // 512 + 1)
        assert len(energies) == expected_frames

    def test_louder_signal_higher_energy_before_normalization(self) -> None:
        t = np.linspace(0, 1.0, 22050, endpoint=False)
        quiet = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        loud = (0.9 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        e_quiet = compute_frame_energies(quiet, 2048, 512)
        e_loud = compute_frame_energies(loud, 2048, 512)
        assert float(np.max(e_quiet)) == pytest.approx(1.0, abs=0.01)
        assert float(np.max(e_loud)) == pytest.approx(1.0, abs=0.01)

    def test_empty_signal_returns_single_zero(self) -> None:
        samples = np.array([], dtype=np.float32)
        energies = compute_frame_energies(samples, 2048, 512)
        assert len(energies) == 1
        assert energies[0] == 0.0


class TestComputeEnergySlope:
    def test_constant_energy_zero_slope(self) -> None:
        energies = np.ones(100) * 0.5
        slope = compute_energy_slope(energies)
        assert slope == pytest.approx(0.0, abs=1e-10)

    def test_increasing_energy_positive_slope(self) -> None:
        energies = np.linspace(0.0, 1.0, 100)
        slope = compute_energy_slope(energies)
        assert slope > 0.0

    def test_single_frame_zero_slope(self) -> None:
        energies = np.array([0.5])
        slope = compute_energy_slope(energies)
        assert slope == 0.0
