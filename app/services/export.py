"""Export writers: M3U8, Rekordbox XML, JSON guide, text cheat sheet."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExportTrack:
    """Track data needed for export."""

    position: int
    title: str
    artist: str
    duration_ms: int
    file_path: str
    bpm: float | None = None
    key_camelot: str | None = None
    energy_lufs: float | None = None
    cue_points: list[dict[str, Any]] = field(default_factory=list)
    saved_loops: list[dict[str, Any]] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)
    mood: str | None = None
    notes: str | None = None
    eq_settings: dict[str, Any] | None = None


@dataclass
class ExportTransition:
    """Transition data between two tracks."""

    from_position: int
    to_position: int
    score: float | None = None
    bpm_delta: float | None = None
    key_distance: int | None = None
    energy_delta: float | None = None
    transition_type: str | None = None
    notes: str | None = None


@dataclass
class SetExportData:
    """Complete set data for export."""

    name: str
    version_label: str | None = None
    quality_score: float | None = None
    tracks: list[ExportTrack] = field(default_factory=list)
    transitions: list[ExportTransition] = field(default_factory=list)


# ── M3U8 Writer ─────────────────────────────────────


def write_m3u8(data: SetExportData, output_path: Path) -> Path:
    """Write extended M3U8 with custom #EXTDJ-* tags."""
    lines = ["#EXTM3U", f"#PLAYLIST:{data.name}"]

    for track in data.tracks:
        duration_sec = (track.duration_ms or 0) // 1000
        lines.append(f"#EXTINF:{duration_sec},{track.artist} - {track.title}")

        if track.bpm:
            lines.append(f"#EXTDJ-BPM:{track.bpm:.1f}")
        if track.key_camelot:
            lines.append(f"#EXTDJ-KEY:{track.key_camelot}")
        if track.energy_lufs is not None:
            lines.append(f"#EXTDJ-ENERGY:{track.energy_lufs:.1f}")

        for cue in track.cue_points:
            lines.append(
                f"#EXTDJ-CUE:{cue.get('position_ms', 0)},"
                f"{cue.get('kind', 0)},{cue.get('label', '')},{cue.get('color', '')}"
            )

        for loop in track.saved_loops:
            lines.append(
                f"#EXTDJ-LOOP:{loop.get('in_ms', 0)},"
                f"{loop.get('out_ms', 0)},{loop.get('label', '')}"
            )

        for section in track.sections:
            lines.append(
                f"#EXTDJ-SECTION:{section.get('type', '')},"
                f"{section.get('start_ms', 0)},{section.get('end_ms', 0)},"
                f"{section.get('energy', '')}"
            )

        # Transition to next track
        trans = next(
            (t for t in data.transitions if t.from_position == track.position),
            None,
        )
        if trans:
            lines.append(
                f"#EXTDJ-TRANSITION:{trans.transition_type or 'mix'},"
                f"{trans.score or 0:.2f},{trans.bpm_delta or 0:.1f},"
                f"{trans.key_distance or 0},{trans.energy_delta or 0:.1f}"
            )

        if track.eq_settings:
            eq_parts = ",".join(f"{k}={v}" for k, v in track.eq_settings.items())
            lines.append(f"#EXTDJ-EQ:{eq_parts}")

        if track.notes:
            lines.append(f"#EXTDJ-NOTE:{track.notes}")

        lines.append(track.file_path)

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


# ── Rekordbox XML Writer ─────────────────────────────


@dataclass
class RekordboxOptions:
    """Configurable inclusion flags for Rekordbox export."""

    include_cue_points: bool = True
    include_saved_loops: bool = True
    include_beatgrid: bool = True
    include_sections: bool = False


def write_rekordbox_xml(
    data: SetExportData,
    output_path: Path,
    options: RekordboxOptions | None = None,
) -> Path:
    """Write Rekordbox-compatible XML."""
    opts = options or RekordboxOptions()

    root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")
    ET.SubElement(root, "PRODUCT", Name="DJ Music Plugin", Version="1.0")
    collection = ET.SubElement(root, "COLLECTION", Entries=str(len(data.tracks)))

    for track in data.tracks:
        attrs = {
            "TrackID": str(track.position + 1),
            "Name": track.title,
            "Artist": track.artist,
            "TotalTime": str((track.duration_ms or 0) // 1000),
            "Location": f"file://localhost{track.file_path}",
        }
        if track.bpm:
            attrs["AverageBpm"] = f"{track.bpm:.2f}"
        if track.key_camelot:
            attrs["Tonality"] = track.key_camelot

        track_el = ET.SubElement(collection, "TRACK", **attrs)

        if opts.include_beatgrid and track.bpm:
            ET.SubElement(
                track_el,
                "TEMPO",
                Inizio="0.000",
                Bpm=f"{track.bpm:.2f}",
                Battito="1",
            )

        if opts.include_cue_points:
            for cue in track.cue_points:
                ET.SubElement(
                    track_el,
                    "POSITION_MARK",
                    Name=cue.get("label", ""),
                    Type=str(cue.get("kind", 0)),
                    Start=f"{cue.get('position_ms', 0) / 1000:.3f}",
                )

        if opts.include_saved_loops:
            for loop in track.saved_loops:
                ET.SubElement(
                    track_el,
                    "POSITION_MARK",
                    Name=loop.get("label", ""),
                    Type="4",  # loop type in Rekordbox
                    Start=f"{loop.get('in_ms', 0) / 1000:.3f}",
                    End=f"{loop.get('out_ms', 0) / 1000:.3f}",
                )

    # Playlist node
    playlists = ET.SubElement(root, "PLAYLISTS")
    root_node = ET.SubElement(playlists, "NODE", Type="0", Name="Root")
    set_node = ET.SubElement(
        root_node,
        "NODE",
        Type="1",
        Name=data.name,
        Entries=str(len(data.tracks)),
    )
    for track in data.tracks:
        ET.SubElement(set_node, "TRACK", Key=str(track.position + 1))

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(str(output_path), encoding="unicode", xml_declaration=True)
    return output_path


# ── JSON Guide Writer ────────────────────────────────


def write_json_guide(data: SetExportData, output_path: Path) -> Path:
    """Write structured JSON with full set details."""
    guide = {
        "set": {
            "name": data.name,
            "version": data.version_label,
            "quality_score": data.quality_score,
            "track_count": len(data.tracks),
        },
        "tracks": [
            {
                "position": t.position + 1,
                "title": t.title,
                "artist": t.artist,
                "bpm": t.bpm,
                "key": t.key_camelot,
                "energy_lufs": t.energy_lufs,
                "mood": t.mood,
                "duration_ms": t.duration_ms,
                "cue_points": t.cue_points,
                "sections": t.sections,
            }
            for t in data.tracks
        ],
        "transitions": [
            {
                "from": tr.from_position + 1,
                "to": tr.to_position + 1,
                "score": tr.score,
                "bpm_delta": tr.bpm_delta,
                "key_distance": tr.key_distance,
                "energy_delta": tr.energy_delta,
                "type": tr.transition_type,
                "notes": tr.notes,
            }
            for tr in data.transitions
        ],
        "analytics": {
            "avg_transition_score": (
                sum(t.score or 0 for t in data.transitions) / max(len(data.transitions), 1)
            ),
            "hard_conflicts": sum(
                1 for t in data.transitions if t.score is not None and t.score == 0.0
            ),
            "bpm_range": (
                [
                    min(t.bpm for t in data.tracks if t.bpm),
                    max(t.bpm for t in data.tracks if t.bpm),
                ]
                if any(t.bpm for t in data.tracks)
                else None
            ),
        },
    }

    output_path.write_text(
        json.dumps(guide, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


# ── Cheat Sheet Writer ───────────────────────────────


def write_cheat_sheet(data: SetExportData, output_path: Path) -> Path:
    """Write human-readable text cheat sheet."""
    lines = [
        f"{'=' * 60}",
        f"  {data.name}",
        f"  Version: {data.version_label or 'N/A'}",
        f"  Score: {data.quality_score or 'N/A'}",
        f"  Tracks: {len(data.tracks)}",
        f"{'=' * 60}",
        "",
    ]

    for _i, track in enumerate(data.tracks):
        bpm_str = f"{track.bpm:.0f}" if track.bpm else "?"
        key_str = track.key_camelot or "?"
        energy_str = f"{track.energy_lufs:.1f}" if track.energy_lufs is not None else "?"

        lines.append(f"{track.position + 1:2d}. {track.artist} - {track.title}")
        lines.append(
            f"    BPM: {bpm_str}  Key: {key_str}  Energy: {energy_str} LUFS"
            f"  Mood: {track.mood or '?'}"
        )

        # Transition info
        trans = next(
            (t for t in data.transitions if t.from_position == track.position),
            None,
        )
        if trans:
            score_str = f"{trans.score:.2f}" if trans.score is not None else "?"
            problems = []
            if trans.score is not None and trans.score == 0.0:
                problems.append("HARD CONFLICT")
            elif trans.score is not None and trans.score < 0.5:
                problems.append("WEAK")

            lines.append(
                f"    → Next: score={score_str}"
                f"  BPM Δ{trans.bpm_delta or 0:+.0f}"
                f"  Key dist={trans.key_distance or '?'}"
                f"  Energy Δ{trans.energy_delta or 0:+.1f}"
                + (f"  ⚠ {', '.join(problems)}" if problems else "")
            )
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
