"""Unit tests for mix_point_service.

Pure compute helpers — no DB, no async. Tests use ``TrackSectionRow``
and plain downbeat lists, no fixtures.
"""

from __future__ import annotations

from app.core.constants import SectionType
from app.services.mix_point_service import (
    TrackSectionRow,
    build_section_context,
    detect_mix_in_point,
    detect_mix_out_point,
    quantize_to_downbeat,
    section_at,
)
from app.transition.section_context import SectionContext

# ── quantize_to_downbeat ─────────────────────────────────────────────


class TestQuantize:
    def test_picks_nearest_downbeat(self) -> None:
        downbeats = [0, 1000, 2000, 3000]
        assert quantize_to_downbeat(1100, downbeats) == 1000
        assert quantize_to_downbeat(1600, downbeats) == 2000

    def test_ties_pick_lower_or_higher_consistently(self) -> None:
        # min() with key= takes the first minimum on tie — that's fine,
        # we just want it to be deterministic.
        downbeats = [0, 1000]
        result = quantize_to_downbeat(500, downbeats)
        assert result in {0, 1000}

    def test_empty_downbeats_returns_input(self) -> None:
        assert quantize_to_downbeat(1234, []) == 1234


# ── detect_mix_out_point ─────────────────────────────────────────────


class TestDetectMixOut:
    def test_outro_section_picked_and_quantised(self) -> None:
        sections = [
            TrackSectionRow(SectionType.INTRO, 0, 30_000),
            TrackSectionRow(SectionType.DROP, 30_000, 200_000),
            TrackSectionRow(SectionType.OUTRO, 200_500, 240_000),
        ]
        # Downbeat at 200_000 is closest to outro start (200_500)
        downbeats = [0, 30_000, 100_000, 200_000, 230_000]
        result = detect_mix_out_point(sections, downbeats, track_duration_ms=240_000)
        assert result == 200_000

    def test_sustain_section_picked_when_no_outro(self) -> None:
        sections = [
            TrackSectionRow(SectionType.INTRO, 0, 30_000),
            TrackSectionRow(SectionType.SUSTAIN, 200_000, 240_000),
        ]
        downbeats = [0, 100_000, 200_000]
        result = detect_mix_out_point(sections, downbeats, track_duration_ms=240_000)
        assert result == 200_000

    def test_fallback_when_no_eligible_section(self) -> None:
        sections = [
            TrackSectionRow(SectionType.DROP, 0, 240_000),
        ]
        downbeats = [0, 50_000, 100_000, 200_000, 230_000]
        result = detect_mix_out_point(sections, downbeats, track_duration_ms=240_000)
        # 30s tail = 210_000 → nearest downbeat 200_000
        assert result == 200_000

    def test_returns_none_without_downbeats_or_sections(self) -> None:
        result = detect_mix_out_point([], [], track_duration_ms=240_000)
        assert result is None

    def test_picks_latest_when_multiple_outros(self) -> None:
        sections = [
            TrackSectionRow(SectionType.OUTRO, 100_000, 150_000),
            TrackSectionRow(SectionType.OUTRO, 200_000, 240_000),
        ]
        downbeats = [0, 100_000, 200_000]
        result = detect_mix_out_point(sections, downbeats, track_duration_ms=240_000)
        assert result == 200_000


# ── detect_mix_in_point ──────────────────────────────────────────────


class TestDetectMixIn:
    def test_intro_section_picked(self) -> None:
        sections = [
            TrackSectionRow(SectionType.INTRO, 200, 30_000),
            TrackSectionRow(SectionType.DROP, 30_000, 200_000),
        ]
        downbeats = [0, 500, 1000, 30_000]
        # Quantise 200 → 0 (nearest downbeat)
        result = detect_mix_in_point(sections, downbeats)
        assert result == 0

    def test_first_downbeat_when_no_intro(self) -> None:
        sections = [
            TrackSectionRow(SectionType.DROP, 0, 240_000),
        ]
        downbeats = [500, 1000, 1500]
        result = detect_mix_in_point(sections, downbeats)
        assert result == 500

    def test_returns_none_without_data(self) -> None:
        assert detect_mix_in_point([], []) is None


# ── section_at + build_section_context ───────────────────────────────


class TestSectionAt:
    def test_finds_containing_section(self) -> None:
        sections = [
            TrackSectionRow(SectionType.INTRO, 0, 30_000),
            TrackSectionRow(SectionType.DROP, 30_000, 200_000),
            TrackSectionRow(SectionType.OUTRO, 200_000, 240_000),
        ]
        assert section_at(15_000, sections) == SectionType.INTRO
        assert section_at(100_000, sections) == SectionType.DROP
        assert section_at(220_000, sections) == SectionType.OUTRO

    def test_returns_none_outside_any_section(self) -> None:
        assert section_at(99_999, []) is None

    def test_boundary_belongs_to_next_section(self) -> None:
        sections = [
            TrackSectionRow(SectionType.INTRO, 0, 30_000),
            TrackSectionRow(SectionType.DROP, 30_000, 60_000),
        ]
        # 30_000 is the end of INTRO (exclusive) and start of DROP (inclusive)
        assert section_at(30_000, sections) == SectionType.DROP


class TestBuildSectionContext:
    def test_drum_only_pair_detected(self) -> None:
        from_sections = [TrackSectionRow(SectionType.OUTRO, 200_000, 240_000)]
        to_sections = [TrackSectionRow(SectionType.INTRO, 0, 30_000)]
        ctx = build_section_context(
            from_sections=from_sections,
            from_mix_out_ms=210_000,
            to_sections=to_sections,
            to_mix_in_ms=0,
        )
        assert isinstance(ctx, SectionContext)
        assert ctx.from_section == SectionType.OUTRO
        assert ctx.to_section == SectionType.INTRO
        assert ctx.is_drum_only_pair is True

    def test_drop_to_intro_not_drum_only(self) -> None:
        from_sections = [TrackSectionRow(SectionType.DROP, 0, 240_000)]
        to_sections = [TrackSectionRow(SectionType.INTRO, 0, 30_000)]
        ctx = build_section_context(
            from_sections=from_sections,
            from_mix_out_ms=200_000,
            to_sections=to_sections,
            to_mix_in_ms=0,
        )
        assert ctx.is_drum_only_pair is False

    def test_missing_mix_points_yield_none_sections(self) -> None:
        ctx = build_section_context(
            from_sections=[],
            from_mix_out_ms=None,
            to_sections=[],
            to_mix_in_ms=None,
        )
        assert ctx.from_section is None
        assert ctx.to_section is None
        assert ctx.is_drum_only_pair is False
