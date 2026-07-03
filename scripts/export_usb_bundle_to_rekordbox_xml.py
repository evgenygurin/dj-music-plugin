#!/usr/bin/env python3
"""Rebuild a rich rekordbox XML for a prepared audio bundle from USB-only data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from export_track_to_rekordbox_xml import (
    add_tempo_mark,
    anlz_marks_for_track,
    build_xml_track_kwargs,
    cue_rows,
    marker_name,
    resolve_track_location,
    strip_usb_prefix,
)
from pyrekordbox import RekordboxXml
from pyrekordbox.devicelib_plus import DeviceLibraryPlus, models


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Manifest produced by export_folder_to_rekordbox_xml.py",
    )
    parser.add_argument(
        "--db",
        default="/Volumes/USB DISK/PIONEER/rekordbox/exportLibrary.db",
    )
    parser.add_argument(
        "--volume-root",
        default="/Volumes/USB DISK",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def title_keys(entry: dict[str, Any]) -> list[str]:
    raw = str(entry.get("artist_title") or "").strip()
    title = str(entry.get("title") or "").strip()
    keys = [raw, title]
    out: list[str] = []
    seen: set[str] = set()
    for key in keys:
        if not key:
            continue
        norm = strip_usb_prefix(key)
        for variant in {key, norm}:
            if variant and variant not in seen:
                seen.add(variant)
                out.append(variant)
    return out


def build_usb_index(db: DeviceLibraryPlus) -> dict[str, list[models.Content]]:
    index: dict[str, list[models.Content]] = {}
    for content in db.get_content().all():
        raw = (content.title or "").strip()
        for key in {raw, strip_usb_prefix(raw)}:
            if not key:
                continue
            index.setdefault(key, []).append(content)
    return index


def choose_usb_track(
    usb_index: dict[str, list[models.Content]],
    entry: dict[str, Any],
) -> tuple[models.Content | None, str | None]:
    for key in title_keys(entry):
        matches = usb_index.get(key, [])
        if len(matches) == 1:
            return matches[0], f"title={key!r}"
    for key in title_keys(entry):
        matches = usb_index.get(key, [])
        if matches:
            return matches[0], f"title-ambiguous={key!r}"
    return None, None


def export_bundle(
    manifest_path: Path,
    db_path: str,
    volume_root: str,
    output: Path,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    playlist_name = str(manifest.get("playlist_name") or "Imported Bundle")
    entries = list(manifest.get("tracks") or [])

    xml_doc = RekordboxXml(name="dj-music-plugin", version="1.6.0", company="OpenAI")
    playlist = xml_doc.add_playlist(playlist_name, keytype="TrackID")
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    tempo_total = 0
    mark_total = 0

    with DeviceLibraryPlus(db_path) as db:
        usb_index = build_usb_index(db)
        for entry in entries:
            usb_track, matched_by = choose_usb_track(usb_index, entry)
            if usb_track is None:
                unmatched.append(
                    {
                        "order": entry.get("order"),
                        "title": entry.get("artist_title") or entry.get("title"),
                        "reason": "no-usb-match",
                    }
                )
                continue

            location = resolve_track_location(usb_track, volume_root)
            track_kwargs = build_xml_track_kwargs(usb_track, None, location)
            track_kwargs["Comments"] = " | ".join(
                [
                    value
                    for value in [
                        str(track_kwargs.get("Comments") or "").strip(),
                        f"bundle_order={entry.get('order')}",
                        f"bundle_source={Path(entry.get('source_path') or '').name}",
                    ]
                    if value
                ]
            )
            xml_track = xml_doc.add_track(location, **track_kwargs)
            playlist.add_track(int(usb_track.content_id))

            tempo_total += add_tempo_mark(xml_track, usb_track, None)
            performance_marks = anlz_marks_for_track(usb_track)
            cues = cue_rows(db, usb_track.content_id)
            load_markers = [c for c in cues if c.kind == 3]

            for mark in performance_marks:
                end_s = None
                if mark["is_loop"] and mark["loop_time_ms"] not in (-1, 0, 4294967295):
                    end_s = mark["loop_time_ms"] / 1000
                xml_track.add_mark(
                    Name=marker_name(mark),
                    Type="loop" if mark["is_loop"] else "cue",
                    Start=mark["time_ms"] / 1000,
                    End=end_s,
                    Num=mark["hot_cue"] if mark["bank"] == "hotcue" else -1,
                )

            if load_markers:
                start_marker = load_markers[0]
                end_marker = load_markers[1] if len(load_markers) > 1 else None
                xml_track.add_mark(
                    Name="Load",
                    Type="load",
                    Start=(start_marker.inUsec or 0) / 1_000_000,
                    End=((end_marker.inUsec or 0) / 1_000_000) if end_marker else None,
                    Num=-1,
                )

            mark_total += len(performance_marks) + (1 if load_markers else 0)
            matched.append(
                {
                    "order": entry.get("order"),
                    "usb_content_id": int(usb_track.content_id),
                    "title": usb_track.title,
                    "matched_by": matched_by,
                }
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(xml_doc.tostring(), encoding="utf-8")
    return {
        "output": str(output),
        "playlist_name": playlist_name,
        "requested_tracks": len(entries),
        "matched_tracks": len(matched),
        "unmatched_tracks": len(unmatched),
        "tempo_exported": tempo_total,
        "marks_exported": mark_total,
        "matched": matched,
        "unmatched": unmatched,
    }


def main() -> None:
    args = parse_args()
    result = export_bundle(
        manifest_path=args.manifest.resolve(),
        db_path=args.db,
        volume_root=args.volume_root,
        output=args.output.resolve(),
    )
    print(result)


if __name__ == "__main__":
    main()
