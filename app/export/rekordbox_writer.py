"""Rekordbox XML export writer."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from app.export.models import RekordboxOptions, SetExportData


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

        track_el = ET.SubElement(collection, "TRACK", attrib=attrs)

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
