"""Tests for AudioLoader — multi-backend audio file loading."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from app.audio.core.loader import AudioLoader
from app.audio.core.types import AudioSignal


def _write_wav(path: Path, samples: np.ndarray, sr: int = 22050) -> None:
    """Write a mono WAV file."""
    int_samples = (samples * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int_samples.tobytes())


@pytest.fixture
def wav_file(tmp_path: Path) -> Path:
    """Create a test WAV file with 1 second of 440Hz sine."""
    sr = 22050
    t = np.linspace(0, 1.0, sr, endpoint=False)
    samples = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    path = tmp_path / "test.wav"
    _write_wav(path, samples, sr)
    return path


class TestAudioLoader:
    async def test_load_returns_audio_signal(self, wav_file: Path) -> None:
        loader = AudioLoader(target_sr=22050)
        signal = await loader.load(str(wav_file))
        assert isinstance(signal, AudioSignal)

    async def test_load_correct_sample_rate(self, wav_file: Path) -> None:
        loader = AudioLoader(target_sr=22050)
        signal = await loader.load(str(wav_file))
        assert signal.sample_rate == 22050

    async def test_load_mono_signal(self, wav_file: Path) -> None:
        loader = AudioLoader(target_sr=22050)
        signal = await loader.load(str(wav_file))
        assert signal.samples.ndim == 1

    async def test_load_file_not_found(self) -> None:
        loader = AudioLoader(target_sr=22050)
        with pytest.raises(FileNotFoundError):
            await loader.load("/nonexistent/path.wav")

    async def test_load_duration_approximately_correct(self, wav_file: Path) -> None:
        loader = AudioLoader(target_sr=22050)
        signal = await loader.load(str(wav_file))
        assert 0.9 < signal.duration_seconds < 1.1

    async def test_custom_target_sr(self, wav_file: Path) -> None:
        loader = AudioLoader(target_sr=16000)
        signal = await loader.load(str(wav_file))
        assert signal.sample_rate == 16000
        assert len(signal.samples) < 22050

    async def test_file_path_preserved(self, wav_file: Path) -> None:
        loader = AudioLoader(target_sr=22050)
        signal = await loader.load(str(wav_file))
        assert signal.file_path == str(wav_file)
