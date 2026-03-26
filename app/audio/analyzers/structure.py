"""Structure analyzer — energy-based track segmentation using pure numpy.

Detects track sections (intro, build, drop, peak, breakdown, outro, etc.)
by computing a novelty curve from frame-level energy differences,
then classifying segments by energy level relative to track mean.

Sections are defined by ``SectionType`` enum (app/core/constants.py):
  0=intro, 1=attack, 2=build, 3=pre_drop, 4=drop, 5=peak,
  6=breakdown, 7=outro, 8=rise, 9=valley, 10=sustain, 11=ambient

Returns sections as a list of dicts with: section_type, start_ms, end_ms,
energy (0-1 normalized), confidence.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.audio.registry import AnalyzerResult, AudioSignal, BaseAnalyzer
from app.core.constants import SectionType

# Minimum segment duration in seconds — prevents tiny fragments
_MIN_SEGMENT_SECONDS: float = 4.0

# Novelty peak-picking threshold (fraction of max novelty)
_NOVELTY_THRESHOLD: float = 0.3

# Energy thresholds relative to track mean for section classification
_ENERGY_THRESHOLDS: dict[str, float] = {
    "very_low": 0.25,  # below 25% of mean → intro/outro/ambient
    "low": 0.60,  # 25-60% of mean → valley/breakdown
    "mid": 1.00,  # 60-100% of mean → build/sustain
    "high": 1.40,  # 100-140% of mean → drop/attack
    # above 140% → peak
}


@dataclass
class _Segment:
    """Internal segment representation before final classification."""

    start_frame: int
    end_frame: int
    energy: float  # mean energy for this segment (0-1 normalized)


class StructureAnalyzer(BaseAnalyzer):
    """Track structure segmentation using energy-based novelty detection.

    Core analyzer (numpy only, no librosa required).
    """

    name = "structure"
    capabilities = {"structure"}
    required_packages: list[str] = []

    async def analyze(self, signal: AudioSignal) -> AnalyzerResult:
        """Detect structural sections from audio signal."""
        samples = signal.samples
        sr = signal.sample_rate

        if len(samples) == 0:
            return AnalyzerResult(
                analyzer_name=self.name,
                success=False,
                error="Empty audio signal",
            )

        frame_length = 2048
        hop_length = 512
        n_frames = max(1, (len(samples) - frame_length) // hop_length + 1)

        # ── Step 1: Compute frame-level energy ──
        frame_energies = np.zeros(n_frames, dtype=np.float64)
        for i in range(n_frames):
            start = i * hop_length
            end = min(start + frame_length, len(samples))
            frame = samples[start:end]
            frame_energies[i] = float(np.mean(frame**2))

        # Normalize to [0, 1]
        max_energy = float(np.max(frame_energies))
        if max_energy > 0:
            norm_energies = frame_energies / max_energy
        else:
            # Silent signal — return single ambient section
            duration_ms = int(signal.duration_seconds * 1000)
            return AnalyzerResult(
                analyzer_name=self.name,
                features={
                    "sections": [
                        {
                            "section_type": SectionType.AMBIENT,
                            "start_ms": 0,
                            "end_ms": duration_ms,
                            "energy": 0.0,
                            "confidence": 1.0,
                        }
                    ],
                    "section_count": 1,
                },
            )

        # ── Step 2: Smooth energy curve (moving average) ──
        smooth_window = max(1, int(2.0 * sr / hop_length))  # ~2 seconds
        kernel = np.ones(smooth_window) / smooth_window
        smoothed = np.convolve(norm_energies, kernel, mode="same")

        # ── Step 3: Compute novelty curve (absolute energy difference) ──
        novelty = np.abs(np.diff(smoothed, prepend=smoothed[0]))
        # Smooth the novelty curve too
        novelty_smooth_window = max(1, smooth_window // 2)
        novelty_kernel = np.ones(novelty_smooth_window) / novelty_smooth_window
        novelty = np.convolve(novelty, novelty_kernel, mode="same")

        # ── Step 4: Find boundaries via peak-picking on novelty curve ──
        min_segment_frames = max(1, int(_MIN_SEGMENT_SECONDS * sr / hop_length))
        threshold = _NOVELTY_THRESHOLD * float(np.max(novelty)) if np.max(novelty) > 0 else 0.0

        boundaries = [0]  # always start at frame 0
        last_boundary = 0
        for i in range(1, len(novelty) - 1):
            # Local maximum above threshold + minimum distance
            if (
                novelty[i] > threshold
                and novelty[i] > novelty[i - 1]
                and novelty[i] >= novelty[i + 1]
                and (i - last_boundary) >= min_segment_frames
            ):
                boundaries.append(i)
                last_boundary = i
        boundaries.append(n_frames)  # always end at last frame

        # ── Step 5: Create segments with mean energy ──
        segments: list[_Segment] = []
        for idx in range(len(boundaries) - 1):
            seg_start = boundaries[idx]
            seg_end = boundaries[idx + 1]
            if seg_end <= seg_start:
                continue
            seg_energy = float(np.mean(smoothed[seg_start:seg_end]))
            segments.append(_Segment(start_frame=seg_start, end_frame=seg_end, energy=seg_energy))

        if not segments:
            duration_ms = int(signal.duration_seconds * 1000)
            return AnalyzerResult(
                analyzer_name=self.name,
                features={
                    "sections": [
                        {
                            "section_type": SectionType.SUSTAIN,
                            "start_ms": 0,
                            "end_ms": duration_ms,
                            "energy": float(np.mean(smoothed)),
                            "confidence": 0.5,
                        }
                    ],
                    "section_count": 1,
                },
            )

        # ── Step 6: Classify each segment by energy + position ──
        mean_energy = float(np.mean(smoothed))
        total_segments = len(segments)
        sections: list[dict[str, object]] = []

        for idx, seg in enumerate(segments):
            position_ratio = idx / total_segments  # 0.0=start, ~1.0=end
            energy_ratio = seg.energy / (mean_energy + 1e-10)
            section_type, confidence = self._classify_segment(
                energy_ratio, position_ratio, idx, total_segments
            )

            start_ms = int(seg.start_frame * hop_length / sr * 1000)
            end_ms = int(seg.end_frame * hop_length / sr * 1000)
            # Clamp end_ms to actual duration
            end_ms = min(end_ms, int(signal.duration_seconds * 1000))

            sections.append(
                {
                    "section_type": section_type,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "energy": round(seg.energy, 4),
                    "confidence": round(confidence, 4),
                }
            )

        return AnalyzerResult(
            analyzer_name=self.name,
            features={
                "sections": sections,
                "section_count": len(sections),
            },
        )

    @staticmethod
    def _classify_segment(
        energy_ratio: float,
        position_ratio: float,
        idx: int,
        total: int,
    ) -> tuple[int, float]:
        """Classify a segment based on energy level and position in track.

        Returns (section_type: int, confidence: float).
        """
        is_first = idx == 0
        is_last = idx == total - 1
        is_early = position_ratio < 0.2
        is_late = position_ratio > 0.8

        # Very low energy at start → intro
        if energy_ratio < _ENERGY_THRESHOLDS["very_low"]:
            if is_first or is_early:
                return SectionType.INTRO, 0.85
            if is_last or is_late:
                return SectionType.OUTRO, 0.85
            return SectionType.AMBIENT, 0.6

        # Low energy → breakdown or valley
        if energy_ratio < _ENERGY_THRESHOLDS["low"]:
            if is_first:
                return SectionType.INTRO, 0.75
            if is_last:
                return SectionType.OUTRO, 0.75
            return SectionType.BREAKDOWN, 0.7

        # Mid energy → build or sustain
        if energy_ratio < _ENERGY_THRESHOLDS["mid"]:
            if is_early:
                return SectionType.BUILD, 0.65
            if is_late:
                return SectionType.BREAKDOWN, 0.6
            return SectionType.SUSTAIN, 0.6

        # High energy → drop or attack
        if energy_ratio < _ENERGY_THRESHOLDS["high"]:
            if is_early:
                return SectionType.ATTACK, 0.65
            return SectionType.DROP, 0.7

        # Very high energy → peak
        return SectionType.PEAK, 0.75
