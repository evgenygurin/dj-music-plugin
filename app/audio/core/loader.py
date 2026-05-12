"""Multi-backend audio file loader.

Extracted from AnalysisPipeline._load_audio() (70 lines, SRP violation).
Fallback chain: soundfile -> librosa -> wave (stdlib).
Resamples to target sample rate if needed.

Zero app/ dependencies — target_sr passed as constructor parameter.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from app.audio.core.types import AudioSignal

log = logging.getLogger(__name__)


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

        Exception policy: only ``ImportError`` (the optional extra is
        not installed) lets us silently fall through to the next
        backend. Library-specific decode failures
        (``soundfile.LibsndfileError``,
        ``librosa.util.exceptions.ParameterError``) are wrapped into a
        clear ``RuntimeError("audio decode failed: …")`` — the previous
        ``except Exception: pass`` over both backends made a corrupt
        MP3 fall through to ``wave.open`` which then crashed with the
        cryptic ``wave.Error("file does not start with RIFF id")``,
        burying the real codec / numpy ABI / libsndfile error.
        """
        sf_module = None
        try:
            import soundfile as sf

            sf_module = sf
        except ImportError:
            pass

        if sf_module is not None:
            try:
                samples, file_sr = sf_module.read(str(path), dtype="float32", always_2d=True)
                return samples.mean(axis=1), file_sr
            except sf_module.LibsndfileError as e:
                # libsndfile recognised the file but could not decode it
                # (corrupt MP3, unknown subtype, missing codec). Surface
                # the real error rather than masking it with a fall-
                # through to ``wave.open``.
                log.warning("soundfile decode failed for %s: %s", path, e)
                msg = f"audio decode failed: {e}"
                raise RuntimeError(msg) from e
            except RuntimeError:
                # soundfile may raise generic RuntimeError on truly
                # broken inputs — re-raise so it is not swallowed.
                raise

        librosa_module = None
        try:
            import librosa

            librosa_module = librosa
        except ImportError:
            pass

        if librosa_module is not None:
            try:
                samples, file_sr = librosa_module.load(str(path), sr=None, mono=True)
                return samples, int(file_sr)
            except librosa_module.util.exceptions.ParameterError as e:
                log.warning("librosa decode failed for %s: %s", path, e)
                msg = f"audio decode failed: {e}"
                raise RuntimeError(msg) from e

        import wave

        try:
            wf = wave.open(str(path), "rb")  # noqa: SIM115 — wrapped in custom error guard below; manager applied right after
        except wave.Error as e:
            # The stdlib ``wave`` module is WAV-only — anything that
            # isn't a RIFF container (MP3, FLAC, OGG, plain garbage,
            # …) reaches this branch when both ``soundfile`` and
            # ``librosa`` are unavailable. The raw ``wave.Error("file
            # does not start with RIFF id")`` is useless to the caller
            # because it hides the actual cause (missing optional
            # decoder), so wrap it with a hint pointing at the right
            # extra. Same wrapping shape as the soundfile / librosa
            # branches above so downstream error handling can rely on
            # the ``audio decode failed: …`` prefix.
            suffix = path.suffix.lower()
            hint = ""
            if suffix and suffix != ".wav":
                hint = (
                    f" (no decoder for {suffix!r}; install soundfile or "
                    f"librosa via ``uv sync --extra audio``)"
                )
            msg = f"audio decode failed: {e}{hint}"
            raise RuntimeError(msg) from e

        with wf:
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
