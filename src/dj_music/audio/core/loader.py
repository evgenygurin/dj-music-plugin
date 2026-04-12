"""Multi-backend audio file loader.

Extracted from AnalysisPipeline._load_audio() (70 lines, SRP violation).
Fallback chain: soundfile -> librosa -> wave (stdlib).
Resamples to target sample rate if needed.

Zero app/ dependencies — target_sr passed as constructor parameter.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from dj_music.audio.core.types import AudioSignal


class AudioLoader:
    """Load audio files as mono float32 numpy arrays.

    Supports MP3, WAV, FLAC, OGG via soundfile/librosa (preferred)
    or WAV-only via wave module (fallback).
    """

    def __init__(self, target_sr: int = 22050) -> None:
        self._target_sr = target_sr

    async def load(self, file_path: str) -> AudioSignal:
        """Load and resample audio file to mono float32.

        Raises:
            FileNotFoundError: If file does not exist.
        """
        path = Path(file_path)
        if not path.exists():
            msg = f"Audio file not found: {file_path}"
            raise FileNotFoundError(msg)

        samples, file_sr = self._read_file(path)

        if file_sr != self._target_sr:
            samples = self._resample(samples, file_sr, self._target_sr)

        duration = len(samples) / self._target_sr

        return AudioSignal(
            samples=samples,
            sample_rate=self._target_sr,
            duration_seconds=duration,
            file_path=file_path,
        )

    def _read_file(self, path: Path) -> tuple[np.ndarray, int]:
        """Read audio file using fallback chain.

        Returns (mono_samples_float32, original_sample_rate).
        """
        try:
            import soundfile as sf

            samples, file_sr = sf.read(str(path), dtype="float32", always_2d=True)
            return samples.mean(axis=1), file_sr
        except Exception:
            pass

        try:
            import librosa

            samples, file_sr = librosa.load(str(path), sr=None, mono=True)
            return samples, int(file_sr)
        except Exception:
            pass

        import wave

        with wave.open(str(path), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            file_sr = wf.getframerate()
            raw_data = wf.readframes(wf.getnframes())

        dtype: type[np.generic] = np.int16
        if sampwidth == 2:
            dtype = np.int16
        elif sampwidth == 4:
            dtype = np.int32
        else:
            dtype = np.uint8

        samples = np.frombuffer(raw_data, dtype=dtype).astype(np.float32)
        if sampwidth == 1:
            samples = (samples - 128.0) / 128.0
        elif sampwidth == 2:
            samples /= 32768.0
        elif sampwidth == 4:
            samples /= 2147483648.0

        if n_channels > 1:
            samples = samples.reshape(-1, n_channels).mean(axis=1)

        return samples, file_sr

    @staticmethod
    def _resample(samples: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio. Tries librosa first, falls back to linear interp."""
        try:
            import librosa

            result: np.ndarray = librosa.resample(samples, orig_sr=orig_sr, target_sr=target_sr)
            return result
        except ImportError:
            ratio = target_sr / orig_sr
            new_length = int(len(samples) * ratio)
            indices = np.linspace(0, len(samples) - 1, new_length)
            interp = np.interp(indices, np.arange(len(samples)), samples)
            result_arr: np.ndarray = interp.astype(np.float32)
            return result_arr
