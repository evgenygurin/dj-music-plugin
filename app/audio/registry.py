"""Analyzer registry — plugin-based architecture for audio analysis.

Analyzers register themselves with capabilities and required dependencies.
The registry discovers built-in analyzers and checks availability at runtime.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class AudioSignal:
    """Mono audio signal loaded once per pipeline run."""

    samples: np.ndarray  # mono float32
    sample_rate: int
    duration_seconds: float
    file_path: str = ""


@dataclass
class AnalyzerResult:
    """Result from a single analyzer run."""

    analyzer_name: str
    features: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str | None = None


class BaseAnalyzer(ABC):
    """Base class for all audio analyzers."""

    name: str = ""
    capabilities: set[str] = set()
    required_packages: list[str] = []

    @abstractmethod
    async def analyze(self, signal: AudioSignal) -> AnalyzerResult:
        """Run analysis on audio signal."""
        ...

    def is_available(self) -> bool:
        """Check if required packages are installed."""
        for pkg in self.required_packages:
            try:
                __import__(pkg)
            except ImportError:
                return False
        return True


class AnalyzerRegistry:
    """Registry of available audio analyzers."""

    def __init__(self) -> None:
        self._analyzers: dict[str, BaseAnalyzer] = {}

    def register(self, analyzer: BaseAnalyzer) -> None:
        """Register an analyzer instance."""
        self._analyzers[analyzer.name] = analyzer

    def get(self, name: str) -> BaseAnalyzer | None:
        """Get analyzer by name."""
        return self._analyzers.get(name)

    def list_available(self) -> list[str]:
        """List names of analyzers whose dependencies are satisfied."""
        return [name for name, a in self._analyzers.items() if a.is_available()]

    def list_all(self) -> list[str]:
        """List all registered analyzer names."""
        return list(self._analyzers.keys())

    def discover(self) -> None:
        """Register all built-in analyzers."""
        from app.audio.analyzers.energy import EnergyAnalyzer
        from app.audio.analyzers.loudness import LoudnessAnalyzer
        from app.audio.analyzers.spectral import SpectralAnalyzer

        self.register(LoudnessAnalyzer())
        self.register(EnergyAnalyzer())
        self.register(SpectralAnalyzer())

        # Optional analyzers — skip if dependencies missing
        try:
            from app.audio.analyzers.bpm import BPMDetector

            self.register(BPMDetector())
        except ImportError:
            pass
