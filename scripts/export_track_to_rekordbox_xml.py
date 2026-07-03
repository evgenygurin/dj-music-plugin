#!/usr/bin/env python3
"""Export one OneLibrary USB track into a rekordbox-importable XML file."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pyrekordbox import RekordboxXml
from pyrekordbox.devicelib_plus import DeviceLibraryPlus, models
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import dispose, get_session_factory
from app.models.track import Track


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="/Volumes/USB DISK/PIONEER/rekordbox/exportLibrary.db")
    parser.add_argument(
        "--volume-root",
        default="/Volumes/USB DISK",
        help="Mounted root path of the USB volume",
    )
    parser.add_argument("--track-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--playlist-name",
        default="Codex Import",
        help="Playlist name to place the exported track into",
    )
    parser.add_argument(
        "--no-supabase",
        action="store_true",
        help="Disable Supabase enrichment and export only USB/ANLZ data",
    )
    parser.add_argument(
        "--supabase-track-id",
        type=int,
        help="Explicit Supabase track_id to enrich from",
    )
    return parser.parse_args()


@dataclass(slots=True)
class SupabaseTrackRow:
    id: int
    title: str
    sort_title: str | None
    duration_ms: int | None
    created_at: str | None
    updated_at: str | None
    rating: int | None
    feedback_status: str | None
    feedback_notes: str | None
    play_count: int | None
    skip_count: int | None
    bpm: float | None
    key_code: int | None
    camelot: str | None
    key_name: str | None
    mood: str | None
    mood_confidence: float | None
    beatport_genre: str | None
    beatport_sub_genre: str | None
    beatport_label: str | None
    beatport_release: str | None
    beatport_bpm: float | None
    beatport_key: str | None
    beatport_camelot: str | None
    integrated_lufs: float | None
    energy_mean: float | None
    danceability: float | None
    ym_album_title: str | None
    ym_album_genre: str | None
    ym_album_year: int | None
    ym_label: str | None
    ym_release_date: str | None
    ym_explicit: bool | None
    file_path: str | None
    file_uri: str | None
    file_size: int | None
    mime_type: str | None
    bitrate: int | None
    sample_rate: int | None
    channels: int | None
    source_app: str | None
    beatgrid_bpm: float | None
    first_downbeat_ms: float | None
    grid_offset_ms: float | None
    variable_tempo: bool | None
    beatgrid_canonical: bool | None
    artist_names: str | None
    genre_names: str | None
    release_titles: str | None
    track_number: int | None
    release_year: int | None
    release_date: str | None
    external_ids: dict[str, str] | None


SUPABASE_EXPORT_SQL = text(
    """
    with base as (
      select t.id, t.title, t.sort_title, t.duration_ms, t.created_at, t.updated_at,
             tf.rating, tf.status as feedback_status, tf.notes as feedback_notes,
             tf.play_count, tf.skip_count,
             f.bpm, f.key_code, k.camelot, k.name as key_name,
             f.mood, f.mood_confidence, f.beatport_genre, f.beatport_sub_genre,
             f.beatport_label, f.beatport_release, f.beatport_bpm, f.beatport_key,
             f.beatport_camelot, f.integrated_lufs, f.energy_mean, f.danceability,
             ym.album_title as ym_album_title, ym.album_genre as ym_album_genre,
             ym.album_year as ym_album_year, ym.label as ym_label,
             ym.release_date as ym_release_date, ym.explicit as ym_explicit,
             li.file_path, li.file_uri, li.file_size, li.mime_type, li.bitrate,
             li.sample_rate, li.channels, li.source_app,
             bg.bpm as beatgrid_bpm, bg.first_downbeat_ms, bg.grid_offset_ms,
             bg.variable_tempo, bg.canonical as beatgrid_canonical
      from tracks t
      left join track_feedback tf on tf.track_id = t.id
      left join track_audio_features_computed f on f.track_id = t.id
      left join keys k on k.key_code = f.key_code
      left join yandex_metadata ym on ym.track_id = t.id
      left join lateral (
        select *
        from dj_library_items li
        where li.track_id = t.id
        order by li.created_at desc nulls last, li.id desc
        limit 1
      ) li on true
      left join lateral (
        select *
        from dj_beatgrids bg
        where bg.library_item_id = li.id
        order by bg.canonical desc, bg.created_at desc nulls last, bg.id desc
        limit 1
      ) bg on true
      where t.id = :track_id
    ),
    artists as (
      select ta.track_id,
             string_agg(
               a.name,
               ', ' order by case when ta.role = 'primary' then 0 else 1 end, a.name
             ) as artist_names
      from track_artists ta
      join artists a on a.id = ta.artist_id
      where ta.track_id = :track_id
      group by ta.track_id
    ),
    genres as (
      select tg.track_id, string_agg(g.name, ', ' order by g.name) as genre_names
      from track_genres tg
      join genres g on g.id = tg.genre_id
      where tg.track_id = :track_id
      group by tg.track_id
    ),
    releases as (
      select tr.track_id,
             string_agg(
               r.title, ', ' order by r.release_date nulls last, r.title
             ) as release_titles,
             max(tr.track_number) as track_number,
             max(extract(year from r.release_date))::int as release_year,
             max(r.release_date)::text as release_date
      from track_releases tr
      join releases r on r.id = tr.release_id
      where tr.track_id = :track_id
      group by tr.track_id
    ),
    ext as (
      select te.track_id, jsonb_object_agg(te.platform, te.external_id) as external_ids
      from track_external_ids te
      where te.track_id = :track_id
      group by te.track_id
    )
    select
      b.*, a.artist_names, g.genre_names, r.release_titles, r.track_number,
      r.release_year, r.release_date, e.external_ids
    from base b
    left join artists a on a.track_id = b.id
    left join genres g on g.track_id = b.id
    left join releases r on r.track_id = b.id
    left join ext e on e.track_id = b.id
    """
)


def resolve_track_location(track: models.Content, volume_root: str) -> str:
    path = track.path or ""
    if path.startswith("/"):
        return str(Path(volume_root) / path.lstrip("/"))
    return path


def strip_usb_prefix(title: str) -> str:
    return re.sub(r"^\s*\d+\s*-\s*", "", title).strip()


def split_artist_title(value: str) -> tuple[str, str]:
    text = value.strip()
    if " - " in text:
        artist, name = text.split(" - ", 1)
        return artist.strip(), name.strip()
    return "", text


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def format_date(value: str | datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).split(" ", 1)[0]


def file_kind_from_path(path: str | None, mime_type: str | None) -> str | None:
    ext = Path(path or "").suffix.lower()
    if ext == ".mp3" or mime_type == "audio/mpeg":
        return "MP3 File"
    if ext in {".m4a", ".mp4", ".aac"}:
        return "AAC File"
    if ext == ".flac":
        return "FLAC File"
    if ext == ".wav":
        return "WAV File"
    if ext in {".aif", ".aiff"}:
        return "AIFF File"
    if mime_type:
        return mime_type
    return None


def file_kind_from_usb(track: models.Content) -> str | None:
    return {
        1: "MP3 File",
        4: "AAC File",
        5: "FLAC File",
        11: "WAV File",
        12: "AIFF File",
    }.get(getattr(track, "fileType", None))


def build_comments(
    usb_comment: str | None,
    supa: SupabaseTrackRow | None,
) -> str:
    parts: list[str] = []
    if usb_comment and usb_comment.strip():
        parts.append(usb_comment.strip())
    if supa is None:
        return " | ".join(parts)
    if supa.feedback_notes and supa.feedback_notes.strip():
        parts.append(supa.feedback_notes.strip())

    structured: list[str] = []
    if supa.feedback_status:
        structured.append(f"status={supa.feedback_status}")
    if supa.mood:
        structured.append(f"mood={supa.mood}")
    if supa.mood_confidence is not None:
        structured.append(f"mood_conf={supa.mood_confidence:.2f}")
    if supa.beatport_genre:
        structured.append(f"beatport_genre={supa.beatport_genre}")
    if supa.beatport_sub_genre:
        structured.append(f"beatport_subgenre={supa.beatport_sub_genre}")
    if supa.beatport_release:
        structured.append(f"beatport_release={supa.beatport_release}")
    if supa.beatport_label:
        structured.append(f"beatport_label={supa.beatport_label}")
    if supa.integrated_lufs is not None:
        structured.append(f"lufs={supa.integrated_lufs:.2f}")
    if supa.energy_mean is not None:
        structured.append(f"energy={supa.energy_mean:.3f}")
    if supa.danceability is not None:
        structured.append(f"danceability={supa.danceability:.3f}")
    if supa.ym_explicit is not None:
        structured.append(f"explicit={str(supa.ym_explicit).lower()}")
    if supa.channels is not None:
        structured.append(f"channels={supa.channels}")
    if supa.source_app:
        structured.append(f"source_app={supa.source_app}")
    if supa.external_ids:
        for platform, external_id in sorted(supa.external_ids.items()):
            structured.append(f"{platform}={external_id}")

    if structured:
        parts.append(" | ".join(structured))
    return " | ".join(parts)


def build_xml_track_kwargs(
    track: models.Content,
    supa: SupabaseTrackRow | None,
    location: str,
) -> dict[str, Any]:
    source_title = (
        first_non_empty(supa.title if supa else None, track.title, Path(location).stem) or ""
    )
    artist_from_title, name_from_title = split_artist_title(str(source_title))
    artist = first_non_empty(
        supa.artist_names if supa else None,
        track.artist_name,
        artist_from_title,
    ) or ""
    name = str(source_title)
    if artist and name.startswith(f"{artist} - "):
        name = name[len(artist) + 3 :].strip()
    elif name_from_title and artist_from_title:
        name = name_from_title

    total_time = first_non_empty(
        round((supa.duration_ms or 0) / 1000) if supa and supa.duration_ms else None,
        track.length,
    )
    bpm = first_non_empty(
        supa.bpm if supa else None,
        supa.beatport_bpm if supa else None,
        (track.bpmx100 / 100) if track.bpmx100 else None,
    )
    tonality = first_non_empty(
        track.key.name if track.key else None,
        supa.beatport_key if supa else None,
        supa.key_name if supa else None,
        supa.camelot if supa else None,
        supa.beatport_camelot if supa else None,
    )
    kwargs: dict[str, Any] = {
        "TrackID": track.content_id,
        "Name": name,
        "Artist": artist,
        "Composer": "",
        "Album": first_non_empty(
            supa.release_titles if supa else None,
            supa.ym_album_title if supa else None,
            track.album_name,
        )
        or "",
        "Grouping": first_non_empty(supa.mood if supa else None, "") or "",
        "Genre": first_non_empty(
            supa.genre_names if supa else None,
            supa.beatport_sub_genre if supa else None,
            supa.beatport_genre if supa else None,
            supa.ym_album_genre if supa else None,
            track.genre_name,
        )
        or "",
        "Kind": first_non_empty(
            file_kind_from_path(
                supa.file_path if supa else None,
                supa.mime_type if supa else None,
            ),
            file_kind_from_usb(track),
            "MP3 File",
        ),
        "Size": first_non_empty(supa.file_size if supa else None, track.fileSize, None),
        "TotalTime": total_time or 0,
        "DiscNumber": first_non_empty(track.discNo, 0) or 0,
        "TrackNumber": first_non_empty(supa.track_number if supa else None, track.trackNo, 0) or 0,
        "Year": first_non_empty(
            supa.release_year if supa else None,
            supa.ym_album_year if supa else None,
            track.releaseYear,
            0,
        )
        or 0,
        "AverageBpm": bpm or 0,
        "DateModified": first_non_empty(format_date(supa.updated_at if supa else None), None),
        "DateAdded": first_non_empty(format_date(supa.created_at if supa else None), None),
        "BitRate": first_non_empty(supa.bitrate if supa else None, track.bitrate, 0) or 0,
        "SampleRate": first_non_empty(
            supa.sample_rate if supa else None,
            getattr(track, "samplingRate", None),
            0,
        )
        or 0,
        "Comments": build_comments(track.djComment, supa),
        "PlayCount": first_non_empty(
            supa.play_count if supa else None,
            getattr(track, "djPlayCount", None),
            0,
        )
        or 0,
        "Rating": first_non_empty(supa.rating if supa else None, track.rating, 0) or 0,
        "Label": first_non_empty(
            supa.beatport_label if supa else None,
            supa.ym_label if supa else None,
            track.label_name,
        )
        or "",
        "Remixer": first_non_empty(track.remixer_name, "") or "",
        "Tonality": tonality or "",
        "Mix": "",
    }
    return {key: value for key, value in kwargs.items() if value is not None}


async def resolve_supabase_track_id(
    session: AsyncSession,
    usb_track: models.Content,
    explicit_track_id: int | None,
) -> tuple[int | None, str | None]:
    if explicit_track_id is not None:
        return explicit_track_id, "explicit"

    candidates = [strip_usb_prefix(usb_track.title or ""), (usb_track.title or "").strip()]
    seen: set[str] = set()
    for title in candidates:
        if not title or title in seen:
            continue
        seen.add(title)
        rows = list(
            (
                await session.execute(
                    select(Track.id)
                    .where(Track.title == title)
                    .order_by(Track.updated_at.desc())
                    .limit(2)
                )
            )
            .scalars()
            .all()
        )
        if rows:
            return int(rows[0]), f"title={title!r}"

    stripped = strip_usb_prefix(usb_track.title or "")
    if stripped:
        fuzzy = list(
            (
                await session.execute(
                    select(Track.id)
                    .where(Track.title.ilike(f"%{stripped}%"))
                    .order_by(Track.updated_at.desc())
                    .limit(2)
                )
            )
            .scalars()
            .all()
        )
        if len(fuzzy) == 1:
            return int(fuzzy[0]), f"ilike={stripped!r}"
    return None, None


async def fetch_supabase_row(track_id: int) -> SupabaseTrackRow | None:
    factory = get_session_factory()
    async with factory() as session:
        row = (
            await session.execute(SUPABASE_EXPORT_SQL, {"track_id": track_id})
        ).mappings().first()
    if row is None:
        return None
    return SupabaseTrackRow(**dict(row))


async def enrich_from_supabase(
    usb_track: models.Content,
    explicit_track_id: int | None,
) -> tuple[SupabaseTrackRow | None, dict[str, Any]]:
    factory = get_session_factory()
    async with factory() as session:
        track_id, matched_by = await resolve_supabase_track_id(
            session,
            usb_track,
            explicit_track_id,
        )
    if track_id is None:
        return None, {"enabled": True, "matched": False}
    row = await fetch_supabase_row(track_id)
    if row is None:
        return None, {"enabled": True, "matched": False, "track_id": track_id}
    return row, {"enabled": True, "matched": True, "track_id": track_id, "matched_by": matched_by}


async def load_supabase_enrichment(
    usb_track: models.Content,
    explicit_track_id: int | None,
) -> tuple[SupabaseTrackRow | None, dict[str, Any]]:
    try:
        return await enrich_from_supabase(usb_track, explicit_track_id)
    finally:
        await dispose()


def cue_rows(db: DeviceLibraryPlus, content_id: int) -> list[models.Cue]:
    return list(db.get_cue(content_id=content_id).order_by("cue_id").all())


def load_raw_dump_module() -> Any:
    dump_path = Path(__file__).resolve().parent / "dump_anlz_cues.py"
    spec = importlib.util.spec_from_file_location("dump_anlz_cues", dump_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {dump_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def anlz_marks_for_track(track: models.Content) -> list[dict[str, Any]]:
    analysis_path = track.analysisDataFilePath
    if not analysis_path:
        return []

    ext_path = Path("/Volumes/USB DISK") / analysis_path.lstrip("/")
    ext_path = ext_path.with_suffix(".EXT")
    if not ext_path.exists():
        return []

    dump_module = load_raw_dump_module()
    raw = dump_module.raw_dump(ext_path)

    marks: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int, int, int]] = set()
    for tag in raw.get("PCOB", []):
        cue_type = tag["cue_type"]
        for entry in tag["entries"]:
            bank = "hotcue" if cue_type == 1 else "memory"
            key = (bank, entry["hot_cue"], entry["type"], entry["time_ms"])
            seen_keys.add(key)
            marks.append(
                {
                    "bank": bank,
                    "hot_cue": entry["hot_cue"],
                    "is_loop": entry["type"] == 2,
                    "time_ms": entry["time_ms"],
                    "loop_time_ms": entry["loop_time_ms"],
                    "comment": "",
                    "color": None,
                }
            )

    color_by_key: dict[tuple[int, int, int], dict[str, Any]] = {}
    for tag in raw.get("PCO2", []):
        bank = "hotcue" if tag.get("object_type") == 1 else "memory"
        for entry in tag["entries"]:
            color_by_key[(entry["hot_cue"], entry["time_ms"], entry["type"])] = {
                "comment": entry["comment"],
                "color": (
                    entry["color_red"],
                    entry["color_green"],
                    entry["color_blue"],
                ),
            }
            key = (bank, entry["hot_cue"], entry["type"], entry["time_ms"])
            if key not in seen_keys:
                seen_keys.add(key)
                marks.append(
                    {
                        "bank": bank,
                        "hot_cue": entry["hot_cue"],
                        "is_loop": entry["type"] == 2,
                        "time_ms": entry["time_ms"],
                        "loop_time_ms": entry["loop_time_ms"],
                        "comment": entry["comment"],
                        "color": (
                            entry["color_red"],
                            entry["color_green"],
                            entry["color_blue"],
                        ),
                    }
                )

    for mark in marks:
        type_code = 2 if mark["is_loop"] else 1
        extra = color_by_key.get((mark["hot_cue"], mark["time_ms"], type_code))
        if extra:
            mark["comment"] = extra["comment"]
            mark["color"] = extra["color"]

    return marks


def anlz_tempos_for_track(track: models.Content) -> list[dict[str, Any]]:
    analysis_path = track.analysisDataFilePath
    if not analysis_path:
        return []
    dat_path = Path("/Volumes/USB DISK") / analysis_path.lstrip("/")
    if not dat_path.exists():
        return []
    dump_module = load_raw_dump_module()
    raw = dump_module.raw_dump(dat_path)
    tempos: list[dict[str, Any]] = []
    for tag in raw.get("PQTZ", []):
        for entry in tag["entries"]:
            tempos.append(
                {
                    "beat": entry["beat"],
                    "bpm": entry["bpm"],
                    "time_ms": entry["time_ms"],
                }
            )
    return tempos


def marker_name(mark: dict[str, Any]) -> str:
    comment = str(mark.get("comment") or "").strip()
    if comment:
        return comment
    if mark["bank"] == "hotcue":
        kind = "Loop" if mark["is_loop"] else "Cue"
        return f"Hot {kind} {mark['hot_cue']}"
    kind = "Memory Loop" if mark["is_loop"] else "Memory Cue"
    return kind


def add_tempo_mark(xml_track: Any, track: models.Content, supa: SupabaseTrackRow | None) -> int:
    anlz_tempos = anlz_tempos_for_track(track)
    if anlz_tempos:
        for entry in anlz_tempos:
            beat = int(entry["beat"] or 1)
            battito = beat if 1 <= beat <= 4 else 1
            xml_track.add_tempo(
                Inizio=entry["time_ms"] / 1000,
                Bpm=float(entry["bpm"]),
                Metro="4/4",
                Battito=battito,
            )
        return len(anlz_tempos)

    start_s = 0.0
    bpm = None
    if supa is not None:
        bpm = first_non_empty(supa.beatgrid_bpm, supa.bpm, supa.beatport_bpm)
        if supa.first_downbeat_ms is not None:
            start_s = max(0.0, supa.first_downbeat_ms / 1000)
        elif supa.grid_offset_ms is not None:
            start_s = max(0.0, supa.grid_offset_ms / 1000)
    if bpm is None and track.bpmx100:
        bpm = track.bpmx100 / 100
    if bpm is None:
        return 0
    xml_track.add_tempo(Inizio=start_s, Bpm=float(bpm), Metro="4/4", Battito=1)
    return 1


def export_track(
    db_path: str,
    volume_root: str,
    track_id: int,
    output: Path,
    playlist_name: str,
    use_supabase: bool,
    supabase_track_id: int | None,
) -> dict[str, Any]:
    xml_doc = RekordboxXml(name="dj-music-plugin", version="1.6.0", company="OpenAI")

    with DeviceLibraryPlus(db_path) as db:
        track = db.get_content(id=track_id)
        if track is None:
            raise SystemExit(f"track_id={track_id} not found")

        supabase_meta: SupabaseTrackRow | None = None
        supabase_result: dict[str, Any] = {"enabled": False}
        if use_supabase:
            supabase_meta, supabase_result = asyncio.run(
                load_supabase_enrichment(track, explicit_track_id=supabase_track_id)
            )

        location = resolve_track_location(track, volume_root)
        xml_track = xml_doc.add_track(
            location,
            **build_xml_track_kwargs(track, supabase_meta, location),
        )
        tempo_count = add_tempo_mark(xml_track, track, supabase_meta)

        cues = cue_rows(db, track.content_id)
        load_markers = [c for c in cues if c.kind == 3]
        performance_marks = anlz_marks_for_track(track)

        for mark in performance_marks:
            start_s = mark["time_ms"] / 1000
            end_ms = mark["loop_time_ms"]
            end_s = None
            if mark["is_loop"] and end_ms not in (-1, 0, 4294967295):
                end_s = end_ms / 1000
            hot_num = mark["hot_cue"] if mark["bank"] == "hotcue" else -1
            mark_type = "loop" if mark["is_loop"] else "cue"
            xml_track.add_mark(
                Name=marker_name(mark),
                Type=mark_type,
                Start=start_s,
                End=end_s,
                Num=hot_num,
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

        playlist = xml_doc.add_playlist(playlist_name, keytype="TrackID")
        playlist.add_track(track.content_id)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(xml_doc.tostring(), encoding="utf-8")

    return {
        "output": str(output),
        "track_id": track_id,
        "playlist": playlist_name,
        "tempo_exported": tempo_count,
        "marks_exported": len(performance_marks) + (1 if load_markers else 0),
        "supabase": supabase_result,
    }


def main() -> None:
    args = parse_args()
    result = export_track(
        db_path=args.db,
        volume_root=args.volume_root,
        track_id=args.track_id,
        output=args.output,
        playlist_name=args.playlist_name,
        use_supabase=not args.no_supabase,
        supabase_track_id=args.supabase_track_id,
    )
    print(result)


if __name__ == "__main__":
    main()
