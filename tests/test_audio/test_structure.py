"""Tests for StructureAnalyzer — energy-based track segmentation.

Uses synthetic audio signals with known energy patterns:
- Constant amplitude sine: should produce few sections
- Fade-in/fade-out: should detect intro/outro-like sections
- Multi-section: alternating loud/quiet blocks → multiple sections
"""

from __future__ import annotations

import numpy as np

from app.audio.analyzers.structure import StructureAnalyzer
from app.audio.core import AudioSignal
from app.audio.core.context import AnalysisContext
from app.core.constants import SectionType

SAMPLE_RATE = 22050
DURATION = 10.0  # seconds — longer than typical test to allow section detection


def _make_signal(samples: np.ndarray) -> AudioSignal:
    """Helper to create AudioSignal from numpy array."""
    return AudioSignal(
        samples=samples.astype(np.float32),
        sample_rate=SAMPLE_RATE,
        duration_seconds=len(samples) / SAMPLE_RATE,
    )


def _run(analyzer: StructureAnalyzer, signal: AudioSignal) -> object:  # type: ignore[type-arg]
    """Run analyzer synchronously via new API."""
    return analyzer.run(AnalysisContext(signal))


def _sine_wave(
    freq: float = 440.0, amplitude: float = 0.5, duration: float = DURATION
) -> np.ndarray:
    """Generate a pure sine wave."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _multi_section_signal() -> np.ndarray:
    """Generate a signal with distinct energy sections.

    Pattern: quiet(2s) → loud(3s) → quiet(2s) → loud(3s) to simulate
    intro → drop → breakdown → drop structure.
    """
    sections = [
        _sine_wave(amplitude=0.05, duration=2.0),  # quiet intro
        _sine_wave(amplitude=0.8, duration=3.0),  # loud drop
        _sine_wave(amplitude=0.05, duration=2.0),  # quiet breakdown
        _sine_wave(amplitude=0.8, duration=3.0),  # loud drop
    ]
    return np.concatenate(sections)


def _fade_in_signal(duration: float = 10.0) -> np.ndarray:
    """Generate a sine wave with linear fade-in from silence to full amplitude."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    envelope = np.linspace(0.0, 1.0, n_samples)
    return (0.5 * envelope * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


class TestStructureAnalyzer:
    def test_success_on_valid_signal(self) -> None:
        analyzer = StructureAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        assert result.success is True

    def test_empty_signal_fails(self) -> None:
        analyzer = StructureAnalyzer()
        signal = _make_signal(np.array([], dtype=np.float32))
        result = _run(analyzer, signal)
        assert result.success is False

    def test_returns_sections_list(self) -> None:
        analyzer = StructureAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        assert "sections" in result.features
        assert isinstance(result.features["sections"], list)
        assert len(result.features["sections"]) >= 1

    def test_returns_section_count(self) -> None:
        analyzer = StructureAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        assert result.features["section_count"] == len(result.features["sections"])

    def test_section_has_required_fields(self) -> None:
        analyzer = StructureAnalyzer()
        result = _run(analyzer, _make_signal(_sine_wave()))
        section = result.features["sections"][0]
        assert "section_type" in section
        assert "start_ms" in section
        assert "end_ms" in section
        assert "energy" in section
        assert "confidence" in section

    def test_section_type_valid_enum(self) -> None:
        """All section types should be valid SectionType values."""
        analyzer = StructureAnalyzer()
        result = _run(analyzer, _make_signal(_multi_section_signal()))
        valid_types = {e.value for e in SectionType}
        for section in result.features["sections"]:
            assert section["section_type"] in valid_types

    def test_sections_cover_full_duration(self) -> None:
        """First section should start at 0, last should end near signal duration."""
        analyzer = StructureAnalyzer()
        signal = _make_signal(_sine_wave(duration=10.0))
        result = _run(analyzer, signal)
        sections = result.features["sections"]
        assert sections[0]["start_ms"] == 0
        # Last section end should be close to duration (within 1 second tolerance)
        expected_end_ms = int(10.0 * 1000)
        assert abs(sections[-1]["end_ms"] - expected_end_ms) < 1000

    def test_sections_non_overlapping(self) -> None:
        """Sections should not overlap — each start >= previous end."""
        analyzer = StructureAnalyzer()
        result = _run(analyzer, _make_signal(_multi_section_signal()))
        sections = result.features["sections"]
        for i in range(1, len(sections)):
            assert sections[i]["start_ms"] >= sections[i - 1]["end_ms"]

    def test_energy_between_0_and_1(self) -> None:
        """Section energy values should be in [0, 1] range."""
        analyzer = StructureAnalyzer()
        result = _run(analyzer, _make_signal(_multi_section_signal()))
        for section in result.features["sections"]:
            assert 0.0 <= section["energy"] <= 1.0

    def test_confidence_between_0_and_1(self) -> None:
        """Section confidence values should be in [0, 1] range."""
        analyzer = StructureAnalyzer()
        result = _run(analyzer, _make_signal(_multi_section_signal()))
        for section in result.features["sections"]:
            assert 0.0 <= section["confidence"] <= 1.0

    def test_multi_section_detects_multiple(self) -> None:
        """Signal with distinct energy changes should produce multiple sections."""
        analyzer = StructureAnalyzer()
        result = _run(analyzer, _make_signal(_multi_section_signal()))
        # Should detect at least 2 sections (quiet→loud transitions)
        assert len(result.features["sections"]) >= 2

    def test_silent_signal_returns_ambient(self) -> None:
        """Silent signal should be classified as ambient."""
        analyzer = StructureAnalyzer()
        silent = np.zeros(int(SAMPLE_RATE * 5), dtype=np.float32)
        result = _run(analyzer, _make_signal(silent))
        assert result.success is True
        sections = result.features["sections"]
        assert len(sections) == 1
        assert sections[0]["section_type"] == SectionType.AMBIENT

    def test_constant_signal_few_sections(self) -> None:
        """A constant-amplitude sine wave should produce fewer sections than dynamic signal."""
        analyzer = StructureAnalyzer()
        constant_result = _run(analyzer, _make_signal(_sine_wave(duration=10.0)))
        dynamic_result = _run(analyzer, _make_signal(_multi_section_signal()))
        assert (
            constant_result.features["section_count"] <= dynamic_result.features["section_count"]
        )
