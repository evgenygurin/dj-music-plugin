#!/usr/bin/env python3
"""Export a Supabase playlist or set_version into a rekordbox-importable XML file."""

from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from export_track_to_rekordbox_xml import (
    SUPABASE_EXPORT_SQL,
    SupabaseTrackRow,
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
from sqlalchemy import text

from app.db.session import dispose, get_session_factory

PLAYLIST_SQL = text(
    """
    select
      p.id as collection_id,
      p.name as collection_name,
      i.sort_index,
      i.added_at,
      i.track_id,
      t.title
    from dj_playlists p
    join dj_playlist_items i on i.playlist_id = p.id
    join tracks t on t.id = i.track_id
    where p.id = :collection_id
    order by i.sort_index asc, i.id asc
    """
)

SET_VERSION_SQL = text(
    """
    select
      sv.id as collection_id,
      coalesce(sv.label, s.name) as collection_name,
      i.sort_index,
      i.created_at as added_at,
      i.track_id,
      t.title,
      i.mix_in_point_ms,
      i.mix_out_point_ms,
      i.planned_eq,
      i.notes,
      i.pinned
    from dj_set_versions sv
    join dj_sets s on s.id = sv.set_id
    join dj_set_items i on i.version_id = sv.id
    join tracks t on t.id = i.track_id
    where sv.id = :collection_id
    order by i.sort_index asc, i.id asc
    """
)


@dataclass(slots=True)
class CollectionItem:
    track_id: int
    title: str
    sort_index: int
    collection_name: str
    added_at: str | None = None
    mix_in_point_ms: int | None = None
    mix_out_point_ms: int | None = None
    planned_eq: str | None = None
    notes: str | None = None
    pinned: bool | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="/Volumes/USB DISK/PIONEER/rekordbox/exportLibrary.db")
    parser.add_argument("--volume-root", default="/Volumes/USB DISK")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--playlist-name", help="Override playlist name inside the rekordbox XML")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--playlist-id", type=int)
    group.add_argument("--set-version-id", type=int)
    return parser.parse_args()


async def fetch_collection_items(
    *,
    playlist_id: int | None,
    set_version_id: int | None,
) -> tuple[str, list[CollectionItem], str]:
    query = PLAYLIST_SQL if playlist_id is not None else SET_VERSION_SQL
    collection_id = playlist_id if playlist_id is not None else set_version_id
    collection_type = "playlist" if playlist_id is not None else "set_version"
    factory = get_session_factory()
    async with factory() as session:
        rows = (await session.execute(query, {"collection_id": collection_id})).mappings().all()

    if not rows:
        raise SystemExit(f"{collection_type} id={collection_id} not found or empty")

    items = [
        CollectionItem(
            track_id=int(row["track_id"]),
            title=str(row["title"]),
            sort_index=int(row["sort_index"]),
            collection_name=str(row["collection_name"]),
            added_at=str(row["added_at"]) if row.get("added_at") is not None else None,
            mix_in_point_ms=row.get("mix_in_point_ms"),
            mix_out_point_ms=row.get("mix_out_point_ms"),
            planned_eq=row.get("planned_eq"),
            notes=row.get("notes"),
            pinned=row.get("pinned"),
        )
        for row in rows
    ]
    return items[0].collection_name, items, collection_type


async def fetch_supabase_rows(track_ids: list[int]) -> dict[int, SupabaseTrackRow]:
    if not track_ids:
        return {}
    factory = get_session_factory()
    rows_by_id: dict[int, SupabaseTrackRow] = {}
    async with factory() as session:
        for track_id in track_ids:
            row = (
                await session.execute(SUPABASE_EXPORT_SQL, {"track_id": track_id})
            ).mappings().first()
            if row is not None:
                rows_by_id[int(track_id)] = SupabaseTrackRow(**dict(row))
    return rows_by_id


def build_usb_index(db: DeviceLibraryPlus) -> dict[str, list[models.Content]]:
    index: dict[str, list[models.Content]] = defaultdict(list)
    for content in db.get_content().all():
        raw_title = (content.title or "").strip()
        stripped = strip_usb_prefix(raw_title)
        for key in {raw_title, stripped}:
            if key:
                index[key].append(content)
    return index


def choose_usb_content(
    usb_index: dict[str, list[models.Content]],
    supa: SupabaseTrackRow,
) -> tuple[models.Content | None, str | None]:
    candidates = [
        supa.title.strip(),
        strip_usb_prefix(supa.title),
    ]
    seen: set[str] = set()
    for key in candidates:
        if not key or key in seen:
            continue
        seen.add(key)
        matches = usb_index.get(key, [])
        if len(matches) == 1:
            return matches[0], f"title={key!r}"
    for key in candidates:
        if not key or key in seen:
            continue
        matches = usb_index.get(key, [])
        if matches:
            return matches[0], f"title-ambiguous={key!r}"
    return None, None


def apply_item_context(
    track_kwargs: dict[str, Any],
    item: CollectionItem,
    collection_type: str,
) -> dict[str, Any]:
    comments = str(track_kwargs.get("Comments") or "").strip()
    extras: list[str] = []
    extras.append(f"{collection_type}_pos={item.sort_index}")
    if item.added_at:
        extras.append(f"added_at={item.added_at}")
    if item.mix_in_point_ms is not None:
        extras.append(f"mix_in_ms={item.mix_in_point_ms}")
    if item.mix_out_point_ms is not None:
        extras.append(f"mix_out_ms={item.mix_out_point_ms}")
    if item.planned_eq:
        extras.append(f"planned_eq={item.planned_eq}")
    if item.notes:
        extras.append(f"set_notes={item.notes}")
    if item.pinned is not None:
        extras.append(f"pinned={str(item.pinned).lower()}")
    suffix = " | ".join(extras)
    track_kwargs["Comments"] = f"{comments} | {suffix}" if comments else suffix
    return track_kwargs


def append_track_to_xml(
    xml_doc: RekordboxXml,
    db: DeviceLibraryPlus,
    usb_track: models.Content,
    supa: SupabaseTrackRow,
    item: CollectionItem,
    volume_root: str,
    collection_type: str,
) -> dict[str, Any]:
    location = resolve_track_location(usb_track, volume_root)
    track_kwargs = build_xml_track_kwargs(usb_track, supa, location)
    track_kwargs = apply_item_context(track_kwargs, item, collection_type)
    xml_track = xml_doc.add_track(location, **track_kwargs)

    tempo_count = add_tempo_mark(xml_track, usb_track, supa)
    cues = cue_rows(db, usb_track.content_id)
    load_markers = [c for c in cues if c.kind == 3]
    performance_marks = anlz_marks_for_track(usb_track)

    for mark in performance_marks:
        start_s = mark["time_ms"] / 1000
        end_s = None
        end_ms = mark["loop_time_ms"]
        if mark["is_loop"] and end_ms not in (-1, 0, 4294967295):
            end_s = end_ms / 1000
        xml_track.add_mark(
            Name=marker_name(mark),
            Type="loop" if mark["is_loop"] else "cue",
            Start=start_s,
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

    return {
        "tempo_exported": tempo_count,
        "marks_exported": len(performance_marks) + (1 if load_markers else 0),
    }


async def export_collection_async(
    *,
    db_path: str,
    volume_root: str,
    output: Path,
    playlist_id: int | None,
    set_version_id: int | None,
    playlist_name_override: str | None,
) -> dict[str, Any]:
    try:
        collection_name, items, collection_type = await fetch_collection_items(
            playlist_id=playlist_id,
            set_version_id=set_version_id,
        )
        supabase_rows = await fetch_supabase_rows([item.track_id for item in items])
    finally:
        await dispose()

    playlist_name = playlist_name_override or collection_name
    xml_doc = RekordboxXml(name="dj-music-plugin", version="1.6.0", company="OpenAI")

    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    tempo_total = 0
    mark_total = 0

    with DeviceLibraryPlus(db_path) as db:
        usb_index = build_usb_index(db)
        playlist = xml_doc.add_playlist(playlist_name, keytype="TrackID")

        for item in items:
            supa = supabase_rows.get(item.track_id)
            if supa is None:
                unmatched.append(
                    {
                        "track_id": item.track_id,
                        "title": item.title,
                        "reason": "missing-supabase-row",
                    }
                )
                continue

            usb_track, matched_by = choose_usb_content(usb_index, supa)
            if usb_track is None:
                unmatched.append(
                    {"track_id": item.track_id, "title": item.title, "reason": "no-usb-match"}
                )
                continue

            stats = append_track_to_xml(
                xml_doc=xml_doc,
                db=db,
                usb_track=usb_track,
                supa=supa,
                item=item,
                volume_root=volume_root,
                collection_type=collection_type,
            )
            playlist.add_track(usb_track.content_id)
            tempo_total += stats["tempo_exported"]
            mark_total += stats["marks_exported"]
            matched.append(
                {
                    "track_id": item.track_id,
                    "usb_content_id": int(usb_track.content_id),
                    "title": item.title,
                    "matched_by": matched_by,
                }
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(xml_doc.tostring(), encoding="utf-8")
    return {
        "output": str(output),
        "collection_type": collection_type,
        "collection_name": collection_name,
        "playlist_name": playlist_name,
        "requested_tracks": len(items),
        "matched_tracks": len(matched),
        "unmatched_tracks": len(unmatched),
        "tempo_exported": tempo_total,
        "marks_exported": mark_total,
        "matched": matched,
        "unmatched": unmatched,
    }


def export_collection(
    *,
    db_path: str,
    volume_root: str,
    output: Path,
    playlist_id: int | None,
    set_version_id: int | None,
    playlist_name_override: str | None,
) -> dict[str, Any]:
    return asyncio.run(
        export_collection_async(
            db_path=db_path,
            volume_root=volume_root,
            output=output,
            playlist_id=playlist_id,
            set_version_id=set_version_id,
            playlist_name_override=playlist_name_override,
        )
    )


def main() -> None:
    args = parse_args()
    result = export_collection(
        db_path=args.db,
        volume_root=args.volume_root,
        output=args.output,
        playlist_id=args.playlist_id,
        set_version_id=args.set_version_id,
        playlist_name_override=args.playlist_name,
    )
    print(result)


if __name__ == "__main__":
    main()
