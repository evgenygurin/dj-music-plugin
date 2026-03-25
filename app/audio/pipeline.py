"""Analysis pipeline — orchestrates multiple analyzers on an audio file.

Loads audio once, runs all available (or requested) analyzers,
handles partial failures gracefully.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.audio.registry import AnalyzerRegistry, AnalyzerResult, AudioSignal
from app.config import settings


@dataclass
class PipelineResult:
    """Combined result from all analyzers in a pipeline run."""

    results: list[AnalyzerResult] = field(default_factory=list)
    features: dict[str, Any] = field(default_factory=dict)

    @property
    def errors(self) -> list[dict[str, str]]:
        """List failed analyzers with their error messages."""
        return [
            {"analyzer": r.analyzer_name, "error": r.error or "unknown"}
            for r in self.results
            if not r.success
        ]

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)


class AnalysisPipeline:
    """Runs analyzers on audio files and merges results."""

    def __init__(self, registry: AnalyzerRegistry) -> None:
        self.registry = registry

    async def analyze(
        self,
        file_path: str,
        analyzers: list[str] | None = None,
    ) -> PipelineResult:
        """Run analyzers on audio file. Returns combined features."""
        signal = await self._load_audio(file_path)
        results: list[AnalyzerResult] = []

        analyzer_names = analyzers or self.registry.list_available()
        for name in analyzer_names:
            analyzer = self.registry.get(name)
            if analyzer and analyzer.is_available():
                try:
                    result = await analyzer.analyze(signal)
                    results.append(result)
                except Exception as e:
                    results.append(
                        AnalyzerResult(
                            analyzer_name=name,
                            success=False,
                            error=str(e),
                        )
                    )

        return PipelineResult(
            results=results,
            features=self._merge_features(results),
        )

    async def _load_audio(self, file_path: str) -> AudioSignal:
        """Load audio file as mono float32 numpy array.

        Supports MP3, WAV, FLAC, OGG via soundfile/librosa (preferred)
        or WAV-only via wave module (fallback).
        """
        path = Path(file_path)
        if not path.exists():
            msg = f"Audio file not found: {file_path}"
            raise FileNotFoundError(msg)

        sr = settings.audio_sample_rate

        # Try soundfile first (handles WAV, FLAC, OGG natively)
        try:
            import soundfile as sf

            samples, file_sr = sf.read(str(path), dtype="float32", always_2d=True)
            # Mix to mono
            samples = samples.mean(axis=1)
        except Exception:
            # Try librosa (handles MP3 via audioread/ffmpeg)
            try:
                import librosa

                samples, file_sr = librosa.load(str(path), sr=None, mono=True)
            except Exception:
                # Final fallback: wave module (WAV only)
                import wave

                with wave.open(str(path), "rb") as wf:
                    n_channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    file_sr = wf.getframerate()
                    raw_data = wf.readframes(wf.getnframes())

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

        # Resample if needed
        if file_sr != sr:
            try:
                import librosa

                samples = librosa.resample(samples, orig_sr=file_sr, target_sr=sr)
            except ImportError:
                # Simple linear interpolation fallback
                ratio = sr / file_sr
                new_length = int(len(samples) * ratio)
                indices = np.linspace(0, len(samples) - 1, new_length)
                samples = np.interp(indices, np.arange(len(samples)), samples).astype(np.float32)

        duration = len(samples) / sr

        return AudioSignal(
            samples=samples,
            sample_rate=sr,
            duration_seconds=duration,
            file_path=file_path,
        )

    def _merge_features(self, results: list[AnalyzerResult]) -> dict[str, Any]:
        """Merge features from all successful analyzer results."""
        merged: dict[str, Any] = {}
        for result in results:
            if result.success:
                merged.update(result.features)
        return merged
