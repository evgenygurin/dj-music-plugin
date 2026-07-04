#!/usr/bin/env python3
"""Export a local audio folder into a rekordbox-importable XML playlist.

Requires pyrekordbox from git master (DeviceLibraryPlus / devicelib_plus are
not in any PyPI release yet):

    uv pip install "pyrekordbox @ git+https://github.com/dylanljones/pyrekordbox.git@f695541827cc488af267d6ca8a8e0052598d85a0"

Run with the project env sourced (a stale harness DJ_DATABASE_URL otherwise
gives "tenant not found"):

    set -a && . ./.env && set +a && uv run python scripts/export_folder_to_rekordbox_xml.py <folder>

File naming for DB enrichment matching: ``NN_Artist - Title.mp3`` or
``NN. Artist - Title.mp3``; when the DB stores the bare title without the
artist, the matcher falls back to title-only.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from export_track_to_rekordbox_xml import (
    SUPABASE_EXPORT_SQL,
    SupabaseTrackRow,
    build_comments,
    file_kind_from_path,
    first_non_empty,
    format_date,
    split_artist_title,
)
from pyrekordbox import RekordboxXml
from sqlalchemy import select, text

from app.db.session import dispose, get_session_factory
from app.models.track_features import TrackSection
from app.repositories.track_features import TrackFeaturesRepository
from app.shared.constants import SectionType
from app.shared.features import TrackFeatures

SUPPORTED_EXTS = {".mp3", ".m4a", ".aac", ".flac", ".wav", ".aif", ".aiff"}

TRACK_MATCH_SQL = text(
    """
    select t.id
    from tracks t
    left join track_audio_features_computed f on f.track_id = t.id
    where regexp_replace(lower(t.title), '[^a-z0-9]+', '', 'g')
          = regexp_replace(lower(:candidate), '[^a-z0-9]+', '', 'g')
    -- Prefer an analyzed row: title-only matches (artist-less crate names
    -- like "Demons") can collide with a featureless duplicate that happens
    -- to be more recently updated. Rank analyzed rows first, then by
    -- analysis_level, so enrichment (BPM/key/beatgrid) is not lost.
    order by (f.track_id is not null) desc,
             coalesce(f.analysis_level, 0) desc,
             t.updated_at desc nulls last,
             t.id desc
    limit 1
    """
)


@dataclass(slots=True)
class FolderTrackEnrichment:
    track_id: int | None
    supa: SupabaseTrackRow | None
    features: TrackFeatures | None
    sections: list[TrackSection]
    matched_by: str | None


@dataclass(frozen=True, slots=True)
class SyntheticMark:
    name: str
    mark_type: str
    start_s: float
    end_s: float | None
    num: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Folder containing audio files")
    parser.add_argument(
        "--output",
        type=Path,
        help="Output XML path, default: <folder>/rekordbox.xml",
    )
    parser.add_argument(
        "--playlist-name",
        help="Playlist name inside rekordbox XML, default: folder name",
    )
    parser.add_argument(
        "--copy-to",
        type=Path,
        help="Optional staging folder: copy audio files there and point XML to the copied files",
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        help="Optional JSON manifest path, default: <xml-dir>/rekordbox_bundle_manifest.json",
    )
    return parser.parse_args()


def audio_files(folder: Path) -> list[Path]:
    files = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS
    ]
    return sorted(files)


def parse_stem(path: Path) -> tuple[str, str]:
    stem = path.stem
    parts = stem.split("_", 1)
    core = parts[1] if len(parts) == 2 and parts[0].isdigit() else stem
    # Strip numbering prefixes: "NN. " / "NN " (generated-sets), "RRRR "
    # (USB crate rank), "NNW " (07_WEAPONS), then leading "[8A] [126.0]"
    # Camelot/BPM tags (USB crate naming).
    core = re.sub(r"^\d{1,4}W?[.\s]+", "", core)
    core = re.sub(r"^(?:\[[^\]]*\]\s*)+", "", core)
    core = core.replace("_-_", " - ").replace("_", " ").strip()
    if " - " in core:
        artist, title = core.split(" - ", 1)
        return artist.strip(), title.strip()
    return "", core


def ffprobe_json(path: Path) -> dict[str, Any]:
    cmd = [
        "/opt/homebrew/bin/ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def kind_from_suffix(path: Path) -> str:
    return {
        ".mp3": "MP3 File",
        ".m4a": "AAC File",
        ".aac": "AAC File",
        ".flac": "FLAC File",
        ".wav": "WAV File",
        ".aif": "AIFF File",
        ".aiff": "AIFF File",
    }.get(path.suffix.lower(), path.suffix.lower().lstrip("."))


def section_name(section_type: int | None) -> str:
    if section_type is None:
        return "UNKNOWN"
    try:
        return SectionType(section_type).name.title().replace("_", " ")
    except ValueError:
        return f"Section {section_type}"


def dominant_loop_bars(features: TrackFeatures | None) -> int:
    bars = features.dominant_phrase_bars if features else None
    if bars is None:
        return 8
    return max(4, min(int(bars), 16))


def clamp_time_s(value_s: float, total_time_s: float) -> float:
    return max(0.0, min(value_s, total_time_s))


def add_unique_mark(
    marks: list[SyntheticMark],
    seen: set[tuple[str, int, int, int]],
    *,
    name: str,
    mark_type: str,
    start_s: float,
    end_s: float | None,
    num: int,
) -> None:
    start_ms = round(start_s * 1000)
    end_ms = -1 if end_s is None else round(end_s * 1000)
    key = (mark_type, num, start_ms, end_ms)
    if key in seen:
        return
    seen.add(key)
    marks.append(
        SyntheticMark(
            name=name,
            mark_type=mark_type,
            start_s=start_s,
            end_s=end_s,
            num=num,
        )
    )


def first_section_of_type(
    sections: list[TrackSection],
    *section_types: SectionType,
) -> TrackSection | None:
    wanted = {int(section_type) for section_type in section_types}
    for section in sections:
        if section.section_type in wanted:
            return section
    return None


def last_section_of_type(
    sections: list[TrackSection],
    *section_types: SectionType,
) -> TrackSection | None:
    wanted = {int(section_type) for section_type in section_types}
    for section in reversed(sections):
        if section.section_type in wanted:
            return section
    return None


def synthesize_tempos(
    xml_track: Any,
    *,
    supa: SupabaseTrackRow | None,
    total_time_s: float,
) -> int:
    if supa is None:
        return 0
    bpm = first_non_empty(supa.beatgrid_bpm, supa.bpm, supa.beatport_bpm)
    if bpm is None or bpm <= 0:
        return 0

    beat_len_s = 60.0 / float(bpm)
    first_downbeat_s = 0.0
    if supa.first_downbeat_ms is not None:
        first_downbeat_s = max(0.0, supa.first_downbeat_ms / 1000)
    elif supa.grid_offset_ms is not None:
        first_downbeat_s = max(0.0, supa.grid_offset_ms / 1000)

    entries = 0
    beat_index = 0
    time_s = first_downbeat_s
    while time_s <= total_time_s + 0.001:
        xml_track.add_tempo(
            Inizio=round(time_s, 3),
            Bpm=float(bpm),
            Metro="4/4",
            Battito=(beat_index % 4) + 1,
        )
        beat_index += 1
        time_s = first_downbeat_s + beat_index * beat_len_s
        entries += 1
    return entries


def build_synthetic_marks(
    *,
    supa: SupabaseTrackRow | None,
    features: TrackFeatures | None,
    sections: list[TrackSection],
    total_time_s: float,
) -> list[SyntheticMark]:
    if supa is None:
        return []

    bpm = first_non_empty(supa.beatgrid_bpm, supa.bpm, supa.beatport_bpm)
    if bpm is None or bpm <= 0:
        bpm = 128.0
    loop_span_s = dominant_loop_bars(features) * 4 * 60.0 / float(bpm)

    marks: list[SyntheticMark] = []
    seen: set[tuple[str, int, int, int]] = set()

    first_downbeat_s = 0.0
    if supa.first_downbeat_ms is not None:
        first_downbeat_s = max(0.0, supa.first_downbeat_ms / 1000)

    mix_in_s = (
        clamp_time_s(features.mix_in_point_ms / 1000, total_time_s)
        if features and features.mix_in_point_ms is not None
        else first_downbeat_s
    )
    mix_out_s = (
        clamp_time_s(features.mix_out_point_ms / 1000, total_time_s)
        if features and features.mix_out_point_ms is not None
        else total_time_s
    )

    intro = first_section_of_type(
        sections,
        SectionType.INTRO,
        SectionType.ATTACK,
        SectionType.SUSTAIN,
        SectionType.AMBIENT,
    )
    build = first_section_of_type(
        sections,
        SectionType.BUILD,
        SectionType.RISE,
        SectionType.PRE_DROP,
    )
    drop = first_section_of_type(sections, SectionType.DROP, SectionType.PEAK)
    breakdown = first_section_of_type(sections, SectionType.BREAKDOWN, SectionType.VALLEY)
    outro = last_section_of_type(
        sections,
        SectionType.OUTRO,
        SectionType.BREAKDOWN,
        SectionType.VALLEY,
        SectionType.SUSTAIN,
        SectionType.AMBIENT,
    )

    add_unique_mark(
        marks,
        seen,
        name="Memory Cue",
        mark_type="cue",
        start_s=first_downbeat_s,
        end_s=None,
        num=-1,
    )
    add_unique_mark(
        marks,
        seen,
        name="Load",
        mark_type="load",
        start_s=mix_in_s,
        end_s=mix_out_s if mix_out_s > mix_in_s else None,
        num=-1,
    )
    add_unique_mark(
        marks,
        seen,
        name="Hot Cue 1",
        mark_type="cue",
        start_s=mix_in_s,
        end_s=None,
        num=1,
    )
    add_unique_mark(
        marks,
        seen,
        name="Hot Cue 4",
        mark_type="cue",
        start_s=mix_out_s,
        end_s=None,
        num=4,
    )

    if intro is not None:
        intro_start_s = clamp_time_s(intro.start_ms / 1000, total_time_s)
        intro_end_s = clamp_time_s(
            min(intro.end_ms / 1000, intro_start_s + loop_span_s),
            total_time_s,
        )
        add_unique_mark(
            marks,
            seen,
            name="Memory Loop",
            mark_type="loop",
            start_s=intro_start_s,
            end_s=intro_end_s if intro_end_s > intro_start_s else None,
            num=-1,
        )
        add_unique_mark(
            marks,
            seen,
            name="Hot Loop 5",
            mark_type="loop",
            start_s=intro_start_s,
            end_s=intro_end_s if intro_end_s > intro_start_s else None,
            num=5,
        )

    if build is not None:
        build_start_s = clamp_time_s(build.start_ms / 1000, total_time_s)
        build_end_s = clamp_time_s(
            min(build.end_ms / 1000, build_start_s + loop_span_s),
            total_time_s,
        )
        add_unique_mark(
            marks,
            seen,
            name="Hot Cue 2",
            mark_type="cue",
            start_s=build_start_s,
            end_s=None,
            num=2,
        )
        add_unique_mark(
            marks,
            seen,
            name="Hot Loop 6",
            mark_type="loop",
            start_s=build_start_s,
            end_s=build_end_s if build_end_s > build_start_s else None,
            num=6,
        )

    if drop is not None:
        drop_start_s = clamp_time_s(drop.start_ms / 1000, total_time_s)
        drop_end_s = clamp_time_s(
            min(drop.end_ms / 1000, drop_start_s + loop_span_s),
            total_time_s,
        )
        add_unique_mark(
            marks,
            seen,
            name="Hot Cue 3",
            mark_type="cue",
            start_s=drop_start_s,
            end_s=None,
            num=3,
        )
        add_unique_mark(
            marks,
            seen,
            name="Hot Loop 7",
            mark_type="loop",
            start_s=drop_start_s,
            end_s=drop_end_s if drop_end_s > drop_start_s else None,
            num=7,
        )

    if breakdown is not None:
        breakdown_start_s = clamp_time_s(breakdown.start_ms / 1000, total_time_s)
        add_unique_mark(
            marks,
            seen,
            name="Memory Cue",
            mark_type="cue",
            start_s=breakdown_start_s,
            end_s=None,
            num=-1,
        )

    if outro is not None:
        outro_start_s = clamp_time_s(outro.start_ms / 1000, total_time_s)
        outro_end_s = clamp_time_s(
            min(outro.end_ms / 1000, outro_start_s + loop_span_s),
            total_time_s,
        )
        add_unique_mark(
            marks,
            seen,
            name="Hot Loop 8",
            mark_type="loop",
            start_s=outro_start_s,
            end_s=outro_end_s if outro_end_s > outro_start_s else None,
            num=8,
        )

    return marks


async def fetch_folder_enrichment(files: list[Path]) -> dict[Path, FolderTrackEnrichment]:
    if not files:
        return {}

    results: dict[Path, FolderTrackEnrichment] = {}
    factory = get_session_factory()
    try:
        async with factory() as session:
            repo = TrackFeaturesRepository(session)
            track_ids: list[int] = []
            track_id_by_file: dict[Path, int] = {}

            for path in files:
                artist, title = parse_stem(path)
                candidate = f"{artist} - {title}" if artist else title
                # Try "Artist - Title" first, then bare title: many DB rows
                # store the title without the artist (e.g. "Fak That").
                track_id = None
                for cand in dict.fromkeys([candidate, title]):
                    row = (
                        await session.execute(
                            TRACK_MATCH_SQL,
                            {"candidate": cand},
                        )
                    ).first()
                    if row is not None:
                        track_id = int(row[0])
                        candidate = cand
                        break
                if track_id is not None:
                    track_ids.append(track_id)
                    track_id_by_file[path.resolve()] = track_id
                results[path.resolve()] = FolderTrackEnrichment(
                    track_id=track_id,
                    supa=None,
                    features=None,
                    sections=[],
                    matched_by=f"title={candidate!r}" if track_id is not None else None,
                )

            features_by_id = await repo.get_scoring_features_batch(track_ids)
            sections_by_track: dict[int, list[TrackSection]] = {}
            if track_ids:
                section_rows = (
                    (
                        await session.execute(
                            select(TrackSection)
                            .where(TrackSection.track_id.in_(track_ids))
                            .order_by(TrackSection.track_id, TrackSection.start_ms)
                        )
                    )
                    .scalars()
                    .all()
                )
                for section in section_rows:
                    sections_by_track.setdefault(section.track_id, []).append(section)

            for path, track_id in track_id_by_file.items():
                row = (
                    (await session.execute(SUPABASE_EXPORT_SQL, {"track_id": track_id}))
                    .mappings()
                    .first()
                )
                results[path] = FolderTrackEnrichment(
                    track_id=track_id,
                    supa=SupabaseTrackRow(**dict(row)) if row is not None else None,
                    features=features_by_id.get(track_id),
                    sections=sections_by_track.get(track_id, []),
                    matched_by=results[path].matched_by,
                )
    finally:
        await dispose()
    return results


def build_track_kwargs(
    path: Path,
    track_id: int,
    supa: SupabaseTrackRow | None,
    features: TrackFeatures | None,
    matched_by: str | None,
) -> dict[str, Any]:
    artist, title = parse_stem(path)
    probe = ffprobe_json(path)
    fmt = probe.get("format", {})
    streams = probe.get("streams", [])
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

    duration_s = round(float(fmt.get("duration") or 0))
    bitrate = round(int(fmt.get("bit_rate") or 0) / 1000) if fmt.get("bit_rate") else 0
    sample_rate = int(audio_stream.get("sample_rate") or 0)

    source_title = (
        first_non_empty(supa.title if supa else None, f"{artist} - {title}", title) or title
    )
    artist_from_title, name_from_title = split_artist_title(str(source_title))
    xml_artist = (
        first_non_empty(supa.artist_names if supa else None, artist, artist_from_title) or ""
    )
    xml_name = str(source_title)
    if xml_artist and xml_name.startswith(f"{xml_artist} - "):
        xml_name = xml_name[len(xml_artist) + 3 :].strip()
    elif name_from_title and artist_from_title:
        xml_name = name_from_title

    comments = build_comments("", supa)
    extras = [f"source_folder={path.parent.name}"]
    if matched_by:
        extras.append(matched_by)
    if features and features.analysis_level is not None:
        extras.append(f"analysis_level={features.analysis_level}")
    if features and features.dominant_phrase_bars is not None:
        extras.append(f"dominant_phrase_bars={features.dominant_phrase_bars}")
    if features and features.mix_in_point_ms is not None:
        extras.append(f"mix_in_ms={features.mix_in_point_ms}")
    if features and features.mix_out_point_ms is not None:
        extras.append(f"mix_out_ms={features.mix_out_point_ms}")
    if features and features.mix_in_section_type is not None:
        extras.append(f"mix_in_section={section_name(features.mix_in_section_type)}")
    if features and features.mix_out_section_type is not None:
        extras.append(f"mix_out_section={section_name(features.mix_out_section_type)}")
    comments = f"{comments} | {' | '.join(extras)}" if comments else " | ".join(extras)

    return {
        "TrackID": track_id,
        "Name": xml_name,
        "Artist": xml_artist,
        "Album": first_non_empty(
            supa.release_titles if supa else None,
            supa.ym_album_title if supa else None,
            "",
        )
        or "",
        "Genre": first_non_empty(
            supa.genre_names if supa else None,
            supa.beatport_sub_genre if supa else None,
            supa.beatport_genre if supa else None,
            supa.ym_album_genre if supa else None,
            "",
        )
        or "",
        "Grouping": first_non_empty(supa.mood if supa else None, "") or "",
        "Kind": first_non_empty(
            file_kind_from_path(
                supa.file_path if supa else None,
                supa.mime_type if supa else None,
            ),
            kind_from_suffix(path),
        ),
        "Size": first_non_empty(supa.file_size if supa else None, path.stat().st_size),
        "TotalTime": first_non_empty(
            round((supa.duration_ms or 0) / 1000) if supa and supa.duration_ms else None,
            duration_s,
        ),
        "AverageBpm": first_non_empty(
            supa.beatgrid_bpm if supa else None,
            supa.bpm if supa else None,
            supa.beatport_bpm if supa else None,
            0,
        ),
        "BitRate": first_non_empty(supa.bitrate if supa else None, bitrate, 0),
        "SampleRate": first_non_empty(supa.sample_rate if supa else None, sample_rate, 0),
        "Comments": comments,
        "Label": first_non_empty(
            supa.beatport_label if supa else None,
            supa.ym_label if supa else None,
            "",
        )
        or "",
        "Tonality": first_non_empty(
            supa.beatport_key if supa else None,
            supa.key_name if supa else None,
            supa.camelot if supa else None,
            supa.beatport_camelot if supa else None,
            "",
        )
        or "",
        "Year": first_non_empty(
            supa.release_year if supa else None,
            supa.ym_album_year if supa else None,
            0,
        ),
        "TrackNumber": first_non_empty(supa.track_number if supa else None, 0),
        "DateModified": first_non_empty(format_date(supa.updated_at if supa else None), None),
        "DateAdded": first_non_empty(format_date(supa.created_at if supa else None), None),
        "PlayCount": first_non_empty(supa.play_count if supa else None, 0),
        "Rating": first_non_empty(supa.rating if supa else None, 0),
    }


def stage_audio_files(files: list[Path], copy_to: Path | None) -> list[Path]:
    if copy_to is None:
        return files
    copy_to.mkdir(parents=True, exist_ok=True)
    staged: list[Path] = []
    for path in files:
        dest = copy_to / path.name
        if path.resolve() != dest.resolve():
            shutil.copy2(path, dest)
        staged.append(dest)
    return staged


def build_manifest_entries(files: list[Path], staged_files: list[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, (src, staged) in enumerate(zip(files, staged_files, strict=True), start=1):
        artist, title = parse_stem(src)
        entries.append(
            {
                "order": index,
                "source_path": str(src.resolve()),
                "staged_path": str(staged.resolve()),
                "filename": staged.name,
                "artist": artist,
                "title": title,
                "artist_title": f"{artist} - {title}" if artist else title,
            }
        )
    return entries


def export_folder(
    folder: Path,
    output: Path,
    playlist_name: str,
    copy_to: Path | None,
    manifest_output: Path | None,
) -> dict[str, Any]:
    files = audio_files(folder)
    if not files:
        raise SystemExit(f"No audio files found in {folder}")
    staged_files = stage_audio_files(files, copy_to.resolve() if copy_to else None)
    enrichment_by_source = asyncio.run(fetch_folder_enrichment(files))
    manifest_path = (
        manifest_output.resolve()
        if manifest_output
        else output.resolve().parent / "rekordbox_bundle_manifest.json"
    )

    xml_doc = RekordboxXml(name="dj-music-plugin", version="1.6.0", company="OpenAI")
    playlist = xml_doc.add_playlist(playlist_name, keytype="TrackID")

    matched_tracks = 0
    tempo_total = 0
    marks_total = 0

    for index, (source_path, staged_path) in enumerate(
        zip(files, staged_files, strict=True),
        start=1,
    ):
        enrichment = enrichment_by_source.get(
            source_path.resolve(),
            FolderTrackEnrichment(
                track_id=None,
                supa=None,
                features=None,
                sections=[],
                matched_by=None,
            ),
        )
        kwargs = build_track_kwargs(
            staged_path,
            track_id=index,
            supa=enrichment.supa,
            features=enrichment.features,
            matched_by=enrichment.matched_by,
        )
        xml_track = xml_doc.add_track(str(staged_path.resolve()), **kwargs)

        tempo_total += synthesize_tempos(
            xml_track,
            supa=enrichment.supa,
            total_time_s=float(kwargs["TotalTime"] or 0),
        )
        marks = build_synthetic_marks(
            supa=enrichment.supa,
            features=enrichment.features,
            sections=enrichment.sections,
            total_time_s=float(kwargs["TotalTime"] or 0),
        )
        for mark in marks:
            xml_track.add_mark(
                Name=mark.name,
                Type=mark.mark_type,
                Start=round(mark.start_s, 3),
                End=round(mark.end_s, 3) if mark.end_s is not None else None,
                Num=mark.num,
            )
        marks_total += len(marks)
        if enrichment.supa is not None:
            matched_tracks += 1
        playlist.add_track(index)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(xml_doc.tostring(), encoding="utf-8")
    manifest = {
        "playlist_name": playlist_name,
        "source_folder": str(folder.resolve()),
        "staging_folder": str(copy_to.resolve()) if copy_to else None,
        "tracks": build_manifest_entries(files, staged_files),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "output": str(output),
        "manifest": str(manifest_path),
        "playlist_name": playlist_name,
        "tracks_exported": len(files),
        "tracks_enriched": matched_tracks,
        "tempo_entries_exported": tempo_total,
        "marks_exported": marks_total,
        "staged": copy_to is not None,
    }


def main() -> None:
    args = parse_args()
    folder = args.folder.resolve()
    output = args.output.resolve() if args.output else folder / "rekordbox.xml"
    playlist_name = args.playlist_name or folder.name
    result = export_folder(
        folder,
        output,
        playlist_name,
        copy_to=args.copy_to,
        manifest_output=args.manifest_output,
    )
    print(result)


if __name__ == "__main__":
    main()
