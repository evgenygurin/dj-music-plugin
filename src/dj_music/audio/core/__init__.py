"""Core audio types and DSP primitives — Layer 1 (0 app deps)."""

from dj_music.audio.core.context import AnalysisContext
from dj_music.audio.core.framing import compute_energy_slope, compute_frame_energies
from dj_music.audio.core.loader import AudioLoader
from dj_music.audio.core.types import AnalyzerResult, AudioSignal, FrameParams

__all__ = [
    "AnalysisContext",
    "AnalyzerResult",
    "AudioLoader",
    "AudioSignal",
    "FrameParams",
    "compute_energy_slope",
    "compute_frame_energies",
]
