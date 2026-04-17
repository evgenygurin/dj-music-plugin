"""Core audio types and DSP primitives — Layer 1 (0 app deps). v2 port."""

from app.v2.audio.core.context import AnalysisContext
from app.v2.audio.core.framing import compute_energy_slope, compute_frame_energies
from app.v2.audio.core.loader import AudioLoader
from app.v2.audio.core.types import AnalyzerResult, AudioSignal, FrameParams

__all__ = [
    "AnalysisContext",
    "AnalyzerResult",
    "AudioLoader",
    "AudioSignal",
    "FrameParams",
    "compute_energy_slope",
    "compute_frame_energies",
]
