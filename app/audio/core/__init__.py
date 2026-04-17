"""Core audio types and DSP primitives — Layer 1 (0 app deps). v2 port."""

from app.audio.core.context import AnalysisContext
from app.audio.core.framing import compute_energy_slope, compute_frame_energies
from app.audio.core.loader import AudioLoader
from app.audio.core.types import AnalyzerResult, AudioSignal, FrameParams

__all__ = [
    "AnalysisContext",
    "AnalyzerResult",
    "AudioLoader",
    "AudioSignal",
    "FrameParams",
    "compute_energy_slope",
    "compute_frame_energies",
]
