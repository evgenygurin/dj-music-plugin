"""Tests for export writers: M3U8, Rekordbox XML, JSON guide, cheat sheet."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.services.export import (
    ExportTrack,
    ExportTransition,
    RekordboxOptions,
    SetExportData,
    write_cheat_sheet,
    write_json_guide,
    write_m3u8,
    write_rekordbox_xml,
)


@pytest.fixture
def sample_data() -> SetExportData:
    return SetExportData(
        name="Test Set",
        version_label="v1",
        quality_score=0.82,
        tracks=[
            ExportTrack(
                position=0,
                title="Track A",
                artist="Artist 1",
                duration_ms=300000,
                file_path="/music/a.mp3",
                bpm=128.0,
                key_camelot="8A",
                energy_lufs=-8.0,
                mood="driving",
                cue_points=[
                    {"position_ms": 30000, "kind": 1, "label": "Drop", "color": "#FF0000"}
                ],
                sections=[{"type": "intro", "start_ms": 0, "end_ms": 30000, "energy": "0.3"}],
            ),
            ExportTrack(
                position=1,
                title="Track B",
                artist="Artist 2",
                duration_ms=360000,
                file_path="/music/b.mp3",
                bpm=130.0,
                key_camelot="9A",
                energy_lufs=-7.0,
                mood="peak_time",
            ),
        ],
        transitions=[
            ExportTransition(
                from_position=0,
                to_position=1,
                score=0.85,
                bpm_delta=2.0,
                key_distance=1,
                energy_delta=1.0,
                transition_type="mix",
            ),
        ],
    )


# ── M3U8 ─────────────────────────────────────────────


def test_m3u8_header(sample_data: SetExportData, tmp_path: Path) -> None:
    path = write_m3u8(sample_data, tmp_path / "test.m3u8")
    content = path.read_text()
    assert content.startswith("#EXTM3U")
    assert "#PLAYLIST:Test Set" in content


def test_m3u8_track_entries(sample_data: SetExportData, tmp_path: Path) -> None:
    path = write_m3u8(sample_data, tmp_path / "test.m3u8")
    content = path.read_text()
    assert "#EXTINF:300,Artist 1 - Track A" in content
    assert "#EXTDJ-BPM:128.0" in content
    assert "#EXTDJ-KEY:8A" in content
    assert "#EXTDJ-ENERGY:-8.0" in content
    assert "/music/a.mp3" in content


def test_m3u8_transition_tag(sample_data: SetExportData, tmp_path: Path) -> None:
    path = write_m3u8(sample_data, tmp_path / "test.m3u8")
    content = path.read_text()
    assert "#EXTDJ-TRANSITION:" in content


def test_m3u8_cue_points(sample_data: SetExportData, tmp_path: Path) -> None:
    path = write_m3u8(sample_data, tmp_path / "test.m3u8")
    content = path.read_text()
    assert "#EXTDJ-CUE:" in content


def test_m3u8_saved_loops(sample_data: SetExportData, tmp_path: Path) -> None:
    """Saved loops should be exported as #EXTDJ-LOOP tags."""
    sample_data.tracks[0].saved_loops = [{"in_ms": 64000, "out_ms": 80000, "label": "Build"}]
    path = write_m3u8(sample_data, tmp_path / "test.m3u8")
    content = path.read_text()
    assert "#EXTDJ-LOOP:64000,80000,Build" in content


def test_m3u8_section_tags(sample_data: SetExportData, tmp_path: Path) -> None:
    """Sections should be exported as #EXTDJ-SECTION tags."""
    path = write_m3u8(sample_data, tmp_path / "test.m3u8")
    content = path.read_text()
    assert "#EXTDJ-SECTION:intro,0,30000,0.3" in content


def test_m3u8_empty_set(tmp_path: Path) -> None:
    """Empty set should produce valid M3U8 with just header."""
    data = SetExportData(name="Empty Set")
    path = write_m3u8(data, tmp_path / "empty.m3u8")
    content = path.read_text()
    assert content.startswith("#EXTM3U")
    assert "#PLAYLIST:Empty Set" in content
    lines = [line for line in content.strip().split("\n") if not line.startswith("#")]
    assert len(lines) == 0  # no file paths


def test_m3u8_track_without_features(tmp_path: Path) -> None:
    """Track with no audio features should still export without errors."""
    data = SetExportData(
        name="Minimal",
        tracks=[
            ExportTrack(
                position=0,
                title="Unknown",
                artist="Unknown",
                duration_ms=180000,
                file_path="/music/unknown.mp3",
            )
        ],
    )
    path = write_m3u8(data, tmp_path / "minimal.m3u8")
    content = path.read_text()
    assert "/music/unknown.mp3" in content
    assert "#EXTDJ-BPM" not in content
    assert "#EXTDJ-KEY" not in content


def test_m3u8_eq_tag(sample_data: SetExportData, tmp_path: Path) -> None:
    """Planned EQ settings should be exported as #EXTDJ-EQ tag (REQUIREMENTS §9.1)."""
    sample_data.tracks[0].eq_settings = {"low": -3, "mid": 0, "high": 2}
    path = write_m3u8(sample_data, tmp_path / "test.m3u8")
    content = path.read_text()
    assert "#EXTDJ-EQ:" in content


def test_m3u8_note_tag(sample_data: SetExportData, tmp_path: Path) -> None:
    """DJ notes should be exported as #EXTDJ-NOTE tag."""
    sample_data.tracks[0].notes = "Start with low EQ"
    path = write_m3u8(sample_data, tmp_path / "test.m3u8")
    content = path.read_text()
    assert "#EXTDJ-NOTE:Start with low EQ" in content


# ── Rekordbox XML ────────────────────────────────────


def test_rekordbox_valid_xml(sample_data: SetExportData, tmp_path: Path) -> None:
    path = write_rekordbox_xml(sample_data, tmp_path / "test.xml")
    tree = ET.parse(str(path))
    root = tree.getroot()
    assert root.tag == "DJ_PLAYLISTS"


def test_rekordbox_track_count(sample_data: SetExportData, tmp_path: Path) -> None:
    path = write_rekordbox_xml(sample_data, tmp_path / "test.xml")
    tree = ET.parse(str(path))
    collection = tree.find("COLLECTION")
    assert collection is not None
    tracks = collection.findall("TRACK")
    assert len(tracks) == 2


def test_rekordbox_cue_points(sample_data: SetExportData, tmp_path: Path) -> None:
    path = write_rekordbox_xml(sample_data, tmp_path / "test.xml")
    tree = ET.parse(str(path))
    marks = tree.findall(".//POSITION_MARK")
    assert len(marks) >= 1


def test_rekordbox_no_cues_option(sample_data: SetExportData, tmp_path: Path) -> None:
    opts = RekordboxOptions(include_cue_points=False, include_saved_loops=False)
    path = write_rekordbox_xml(sample_data, tmp_path / "test.xml", options=opts)
    tree = ET.parse(str(path))
    marks = tree.findall(".//POSITION_MARK")
    assert len(marks) == 0


# ── JSON Guide ───────────────────────────────────────


def test_json_guide_structure(sample_data: SetExportData, tmp_path: Path) -> None:
    path = write_json_guide(sample_data, tmp_path / "guide.json")
    data = json.loads(path.read_text())
    assert "set" in data
    assert "tracks" in data
    assert "transitions" in data
    assert "analytics" in data
    assert data["set"]["name"] == "Test Set"
    assert len(data["tracks"]) == 2


def test_json_guide_analytics(sample_data: SetExportData, tmp_path: Path) -> None:
    path = write_json_guide(sample_data, tmp_path / "guide.json")
    data = json.loads(path.read_text())
    assert data["analytics"]["hard_conflicts"] == 0
    assert data["analytics"]["avg_transition_score"] > 0


# ── Cheat Sheet ──────────────────────────────────────


def test_cheat_sheet_header(sample_data: SetExportData, tmp_path: Path) -> None:
    path = write_cheat_sheet(sample_data, tmp_path / "cheat.txt")
    content = path.read_text()
    assert "Test Set" in content
    assert "v1" in content


def test_cheat_sheet_tracks(sample_data: SetExportData, tmp_path: Path) -> None:
    path = write_cheat_sheet(sample_data, tmp_path / "cheat.txt")
    content = path.read_text()
    assert "Artist 1 - Track A" in content
    assert "128" in content
    assert "8A" in content


def test_cheat_sheet_transition(sample_data: SetExportData, tmp_path: Path) -> None:
    path = write_cheat_sheet(sample_data, tmp_path / "cheat.txt")
    content = path.read_text()
    assert "score=0.85" in content
