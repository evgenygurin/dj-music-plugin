"""Render a 12-deck prepared-stem performance mix from local stem files.

The script is deliberately local-only: it reads `/Users/laptop/Desktop/Stems`,
builds independent stem events, caps the virtual deck plan at 12 active layers,
and renders one continuous MP3 without demucs or database writes.

Run:
    PATH="/opt/homebrew/bin:$PATH" UV_CACHE_DIR=/tmp/uv-cache \
        uv run --no-sync python scripts/render_12deck_performance_matrix.py
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from itertools import pairwise
from pathlib import Path

from app.audio.render.diagnostics import scan_mix
from app.audio.render.kick_phase import detect_kick_trim
from app.audio.render.phase_refine import refine_phase
from app.domain.render.models import STEM_ORDER

STEMS_DIR = Path("/Users/laptop/Desktop/Stems")
OUT_DIR = Path("generated-sets/12deck-performance-matrix-2026-07-21")
STEM_PATTERN = re.compile(
    r"^(?P<index>\d+)\s+\[(?P<bpm>\d+)bpm\]\s+\[(?P<genre>[\w-]+)\]\s+"
    r"(?P<title>.+)-(?P<stem>acappella|bass|drums|harmonic|instrumental)\.m4a$"
)


@dataclass(slots=True)
class StemTrack:
    index: int
    title: str
    bpm: float
    genre: str
    stems: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StemEvent:
    track_index: int
    title: str
    genre: str
    stem: str
    path: str
    timeline_start_s: float
    duration_s: float
    trim_start_s: float
    source_bpm: float
    target_bpm: float
    gain_db: float
    fade_in_s: float
    fade_out_s: float
    eq_chain: str
    role: str

    @property
    def timeline_end_s(self) -> float:
        return self.timeline_start_s + self.duration_s

    @property
    def tempo_ratio(self) -> float:
        return self.target_bpm / self.source_bpm


def parse_stems(stems_dir: Path) -> list[StemTrack]:
    tracks: dict[int, StemTrack] = {}
    for path in sorted(stems_dir.glob("*.m4a")):
        match = STEM_PATTERN.match(path.name)
        if match is None:
            continue
        idx = int(match.group("index"))
        track = tracks.setdefault(
            idx,
            StemTrack(
                index=idx,
                title=match.group("title"),
                bpm=float(match.group("bpm")),
                genre=match.group("genre"),
            ),
        )
        track.stems[match.group("stem")] = str(path)
    required = set(STEM_ORDER)
    return [track for track in tracks.values() if required.issubset(track.stems)]


def _pick(
    tracks: list[StemTrack],
    *,
    bpm_range: tuple[float, float],
    genres: set[str],
    count: int,
    reverse: bool = False,
    exclude: set[int] | None = None,
) -> list[StemTrack]:
    exclude = exclude or set()
    pool = [
        track
        for track in tracks
        if track.index not in exclude
        and bpm_range[0] <= track.bpm <= bpm_range[1]
        and track.genre in genres
    ]
    pool.sort(key=lambda track: (track.bpm, track.genre, track.index), reverse=reverse)
    picked: list[StemTrack] = []
    seen_genres: set[str] = set()
    for track in pool:
        if track.genre in seen_genres and len(seen_genres) < min(len(genres), count):
            continue
        picked.append(track)
        seen_genres.add(track.genre)
        if len(picked) == count:
            return picked
    for track in pool:
        if track in picked:
            continue
        picked.append(track)
        if len(picked) == count:
            break
    return picked


def curate_track_order(tracks: list[StemTrack]) -> list[StemTrack]:
    """Two BPM stories: slow hypnotic trust-build, bridge, peak warehouse."""
    story1 = _pick(
        tracks,
        bpm_range=(126, 130),
        genres={"hypnotic", "dub_techno", "detroit", "minimal", "progressive", "melodic_deep"},
        count=10,
    )
    used = {track.index for track in story1}
    bridge = _pick(
        tracks,
        bpm_range=(131, 132),
        genres={"acid", "driving", "detroit", "industrial", "progressive", "peak_time"},
        count=2,
        exclude=used,
    )
    used.update(track.index for track in bridge)
    story2 = _pick(
        tracks,
        bpm_range=(133, 140),
        genres={"industrial", "peak_time", "hard_techno", "acid", "driving"},
        count=12,
        exclude=used,
    )
    if len(story1) < 8 or len(bridge) < 1 or len(story2) < 8:
        raise RuntimeError("Not enough compatible complete stem tracks for the performance arc")
    return story1 + bridge + story2


def target_bpm_at(position: int, total: int, start_bpm: float, end_bpm: float) -> float:
    x = position / max(1, total - 1)
    return start_bpm + (end_bpm - start_bpm) * x


def energy_gain_at(position: int, total: int, start_gain_db: float, end_gain_db: float) -> float:
    x = position / max(1, total - 1)
    return start_gain_db + (end_gain_db - start_gain_db) * x


def stem_eq(stem: str) -> str:
    if stem == "drums":
        return "highpass=f=36:t=4,lowpass=f=15500,equalizer=f=260:t=q:w=1.2:g=-1.2"
    if stem == "bass":
        return "highpass=f=30:t=4,lowpass=f=235,equalizer=f=58:t=q:w=1.0:g=0.9"
    if stem == "harmonic":
        return "highpass=f=170:t=4,lowpass=f=10500,equalizer=f=360:t=q:w=1.3:g=-1.0"
    if stem == "instrumental":
        return "highpass=f=230:t=4,lowpass=f=7800,equalizer=f=420:t=q:w=1.2:g=-2.0"
    return "highpass=f=155:t=4,lowpass=f=11200,equalizer=f=280:t=q:w=1.0:g=-1.5"


def stem_base_gain(stem: str) -> float:
    return {
        "drums": -5.0,
        "bass": -6.0,
        "harmonic": -10.0,
        "instrumental": -16.0,
        "acappella": -14.0,
    }[stem]


def add_event(
    events: list[StemEvent],
    track: StemTrack,
    *,
    stem: str,
    start_s: float,
    duration_s: float,
    trim_start_s: float,
    target_bpm: float,
    gain_db: float,
    fade_in_s: float,
    fade_out_s: float,
    role: str,
) -> None:
    if duration_s <= 1.0:
        return
    events.append(
        StemEvent(
            track_index=track.index,
            title=track.title,
            genre=track.genre,
            stem=stem,
            path=track.stems[stem],
            timeline_start_s=max(0.0, start_s),
            duration_s=duration_s if start_s >= 0 else duration_s + start_s,
            trim_start_s=trim_start_s,
            source_bpm=track.bpm,
            target_bpm=target_bpm,
            gain_db=gain_db,
            fade_in_s=max(0.02, fade_in_s),
            fade_out_s=max(0.02, fade_out_s),
            eq_chain=stem_eq(stem),
            role=role,
        )
    )


def resolve_drum_trim(
    track: StemTrack,
    *,
    target_bpm: float,
    cache: dict[str, dict[str, float]],
) -> float:
    key = f"{track.index}:{target_bpm:.3f}"
    if key not in cache:
        try:
            raw_trim = detect_kick_trim(track.stems["drums"], start_s=0.0, bpm=track.bpm)
            delta_ms, refined = refine_phase(
                track.stems["drums"],
                base_trim_s=raw_trim,
                bpm=track.bpm,
                target_bpm=target_bpm,
            )
            trim = max(0.0, min(8.0, refined))
            cache[key] = {
                "raw_trim_s": raw_trim,
                "phase_delta_ms": delta_ms,
                "refined_trim_s": trim,
            }
        except Exception as exc:
            print(f"WARN beatgrid fallback for {track.index} {track.title}: {exc}")
            cache[key] = {"raw_trim_s": 0.0, "phase_delta_ms": 0.0, "refined_trim_s": 0.0}
    return cache[key]["refined_trim_s"]


def build_events(
    track_order: list[StemTrack],
    *,
    start_bpm: float,
    end_bpm: float,
    start_gain_db: float,
    end_gain_db: float,
    beatgrid_cache: dict[str, dict[str, float]],
) -> tuple[list[StemEvent], dict[str, float]]:
    total = len(track_order)
    sync_bpm = (start_bpm + end_bpm) / 2.0
    avg_bpm = 132.0
    beat_s = 60.0 / avg_bpm
    bar_s = beat_s * 4.0
    body_s = 32 * bar_s
    transition_s = 32 * bar_s
    bass_swap_s = 4 * beat_s
    events: list[StemEvent] = []

    for i, track in enumerate(track_order):
        start = i * body_s
        target_bpm = sync_bpm
        energy_gain = energy_gain_at(i, total, start_gain_db, end_gain_db)
        trim_start_s = resolve_drum_trim(track, target_bpm=target_bpm, cache=beatgrid_cache)
        has_prev = i > 0
        has_next = i < total - 1

        drum_start = start - (transition_s if has_prev else 0.0)
        drum_dur = body_s + (transition_s if has_prev else 0.0) + (
            transition_s if has_next else 0.0
        )
        add_event(
            events,
            track,
            stem="drums",
            start_s=drum_start,
            duration_s=drum_dur,
            trim_start_s=trim_start_s,
            target_bpm=target_bpm,
            gain_db=stem_base_gain("drums") + energy_gain,
            fade_in_s=transition_s if has_prev else beat_s,
            fade_out_s=transition_s if has_next else 2 * bar_s,
            role="long_drum_overlay",
        )

        bass_start = start - (bass_swap_s if has_prev else 0.0)
        bass_dur = body_s + (bass_swap_s if has_prev else 0.0) + (
            bass_swap_s if has_next else 0.0
        )
        add_event(
            events,
            track,
            stem="bass",
            start_s=bass_start,
            duration_s=bass_dur,
            trim_start_s=trim_start_s,
            target_bpm=target_bpm,
            gain_db=stem_base_gain("bass") + energy_gain,
            fade_in_s=bass_swap_s if has_prev else bar_s,
            fade_out_s=bass_swap_s if has_next else bar_s,
            role="one_bass_rule",
        )

        for stem, overlap, fade_bars in (
            ("harmonic", 0.85, 16),
            ("instrumental", 0.55, 12),
        ):
            pad = transition_s * overlap
            add_event(
                events,
                track,
                stem=stem,
                start_s=start - (pad if has_prev else 0.0),
                duration_s=body_s + (pad if has_prev else 0.0) + (pad if has_next else 0.0),
                trim_start_s=trim_start_s,
                target_bpm=target_bpm,
                gain_db=stem_base_gain(stem) + energy_gain,
                fade_in_s=fade_bars * bar_s if has_prev else 2 * bar_s,
                fade_out_s=fade_bars * bar_s if has_next else 2 * bar_s,
                role="eq_carved_music_bed",
            )

        if i % 3 == 1 or track.genre in {"hypnotic", "acid", "peak_time"}:
            add_event(
                events,
                track,
                stem="acappella",
                start_s=start + 8 * bar_s,
                duration_s=body_s + 10 * bar_s,
                trim_start_s=trim_start_s,
                target_bpm=target_bpm,
                gain_db=stem_base_gain("acappella") + energy_gain,
                fade_in_s=8 * bar_s,
                fade_out_s=12 * bar_s,
                role="vocal_tease",
            )

        if has_next and i + 2 < total:
            future = track_order[i + 2]
            transition_mid = (i + 1) * body_s - transition_s * 0.25
            add_event(
                events,
                future,
                stem="harmonic",
                start_s=transition_mid,
                duration_s=18 * bar_s,
                trim_start_s=resolve_drum_trim(
                    future,
                    target_bpm=sync_bpm,
                    cache=beatgrid_cache,
                ),
                target_bpm=sync_bpm,
                gain_db=-18.0 + energy_gain_at(i + 2, total, start_gain_db, end_gain_db),
                fade_in_s=6 * bar_s,
                fade_out_s=8 * bar_s,
                role="future_harmonic_tease",
            )

    stats = {
        "body_s": body_s,
        "transition_s": transition_s,
        "bar_s": bar_s,
        "start_bpm": start_bpm,
        "end_bpm": end_bpm,
        "sync_bpm": sync_bpm,
        "start_gain_db": start_gain_db,
        "end_gain_db": end_gain_db,
    }
    return events, stats


def active_count(events: list[StemEvent], time_s: float) -> int:
    return sum(event.timeline_start_s <= time_s < event.timeline_end_s for event in events)


def cap_to_12(events: list[StemEvent]) -> list[StemEvent]:
    priority = {
        "one_bass_rule": 0,
        "long_drum_overlay": 1,
        "eq_carved_music_bed": 2,
        "vocal_tease": 3,
        "future_harmonic_tease": 4,
    }
    points = sorted(
        {
            0.0,
            *[event.timeline_start_s for event in events],
            *[event.timeline_end_s for event in events],
        }
    )
    keep = set(range(len(events)))
    for a, b in pairwise(points):
        if b <= a:
            continue
        mid = (a + b) / 2.0
        active = [
            idx for idx in keep if events[idx].timeline_start_s <= mid < events[idx].timeline_end_s
        ]
        if len(active) <= 12:
            continue
        active.sort(key=lambda idx: (priority[events[idx].role], -events[idx].gain_db))
        for idx in active[12:]:
            keep.discard(idx)
    return [event for idx, event in enumerate(events) if idx in keep]


def filter_complex(events: list[StemEvent]) -> str:
    parts: list[str] = []
    labels: list[str] = []
    for i, event in enumerate(events):
        source_dur = event.duration_s / event.tempo_ratio + 1.0
        delay_ms = int(event.timeline_start_s * 1000)
        fade_out_start = max(0.0, event.duration_s - event.fade_out_s)
        label = f"e{i}"
        parts.append(
            f"[{i}:a]atrim=start={event.trim_start_s:.4f}:duration={source_dur:.3f},"
            f"asetpts=PTS-STARTPTS,"
            f"rubberband=tempo={event.tempo_ratio:.5f}:pitchq=quality,"
            f"atrim=duration={event.duration_s:.3f},asetpts=PTS-STARTPTS,"
            f"{event.eq_chain},"
            f"afade=t=in:curve=qsin:st=0:d={min(event.fade_in_s, event.duration_s / 2):.3f},"
            f"afade=t=out:curve=qsin:st={fade_out_start:.3f}:"
            f"d={min(event.fade_out_s, event.duration_s / 2):.3f},"
            f"volume={event.gain_db:.2f}dB,"
            f"aformat=sample_rates=48000:channel_layouts=stereo,"
            f"adelay={delay_ms}|{delay_ms}[{label}]"
        )
        labels.append(f"[{label}]")
    parts.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=longest,"
        "volume=-6dB,"
        "highpass=f=28:t=4,"
        "firequalizer=gain_entry='entry(35,-1.5);entry(65,0.6);"
        "entry(120,0);entry(250,-1.2);entry(900,-0.6);"
        "entry(3200,0.5);entry(9500,0.9);entry(15000,-0.8)',"
        "acompressor=threshold=-20dB:ratio=1.5:attack=35:release=180:"
        "knee=4:detection=rms:link=average:makeup=1,"
        "alimiter=level_in=1:level_out=1:limit=0.50:attack=8:release=80[mix]"
    )
    return ";".join(parts)


def post_safety_master(in_path: Path, out_path: Path, *, duration_s: float | None = None) -> None:
    filters = []
    if duration_s is not None:
        filters.append(f"atrim=duration={duration_s:.3f},asetpts=PTS-STARTPTS")
    filters.append("loudnorm=I=-14:LRA=5:TP=-3.0:linear=false:print_format=summary")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(in_path),
        "-af",
        ",".join(filters),
        "-c:a",
        "libmp3lame",
        "-b:a",
        "320k",
        "-q:a",
        "0",
        str(out_path),
    ]
    proc = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "")[-4000:])


def render(events: list[StemEvent], out_path: Path, *, duration_s: float | None = None) -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found")
    raw_path = out_path.with_name(f"{out_path.stem}.raw.mp3")
    cmd = [
        "ffmpeg",
        "-y",
        *[arg for event in events for arg in ("-i", event.path)],
        "-filter_complex",
        filter_complex(events),
        "-map",
        "[mix]",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "320k",
        "-q:a",
        "0",
        str(raw_path),
    ]
    proc = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "")[-4000:])
    post_safety_master(raw_path, out_path, duration_s=duration_s)


def join_parts(parts: list[Path], out_path: Path) -> None:
    if len(parts) < 2:
        out_path.write_bytes(parts[0].read_bytes())
        return
    graph_parts: list[str] = []
    previous = "[0:a]"
    for idx in range(1, len(parts)):
        out_label = "[mix]" if idx == len(parts) - 1 else f"[x{idx}]"
        graph_parts.append(
            f"{previous}[{idx}:a]acrossfade=d=16:c1=qsin:c2=qsin{out_label}"
        )
        previous = out_label
    graph_parts.append(
        "[mix]volume=-2dB,"
        "alimiter=level_in=1:level_out=1:limit=0.50:attack=8:release=80[master]"
    )
    raw_path = out_path.with_name(f"{out_path.stem}.raw.mp3")
    cmd = [
        "ffmpeg",
        "-y",
        *[arg for part in parts for arg in ("-i", str(part))],
        "-filter_complex",
        ";".join(graph_parts),
        "-map",
        "[master]",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "320k",
        "-q:a",
        "0",
        str(raw_path),
    ]
    proc = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "")[-4000:])
    post_safety_master(raw_path, out_path)


def chunked(section: list[StemTrack], size: int) -> list[list[StemTrack]]:
    return [section[i : i + size] for i in range(0, len(section), size)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stems-dir", type=Path, default=STEMS_DIR)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--max-parts", type=int, default=None)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    tracks = parse_stems(args.stems_dir)
    order = curate_track_order(tracks)
    section_specs = [
        ("story1_nina_hypnotic", order[:10], 128.0, 130.0, -3.0, -1.5, 10),
        ("bridge_132", order[10:12], 132.0, 132.0, -2.0, -1.0, 2),
        ("story2_liebing_peak", order[12:], 133.0, 137.0, -1.5, 0.0, 12),
    ]
    part_paths: list[Path] = []
    section_manifests: list[dict[str, object]] = []
    all_events: list[StemEvent] = []
    all_active_counts: list[int] = []
    rendered_parts = 0
    beatgrid_cache: dict[str, dict[str, float]] = {}

    for name, section_order, bpm_a, bpm_b, gain_a, gain_b, chunk_size in section_specs:
        section_chunks = chunked(section_order, chunk_size)
        for chunk_index, section_chunk in enumerate(section_chunks, start=1):
            if args.max_parts is not None and rendered_parts >= args.max_parts:
                break
            suffix = f"_{chunk_index:02d}" if len(section_chunks) > 1 else ""
            chunk_name = f"{name}{suffix}"
            chunk_start = (chunk_index - 1) / max(1, len(section_chunks))
            chunk_end = chunk_index / max(1, len(section_chunks))
            chunk_bpm_a = bpm_a
            chunk_bpm_b = bpm_b
            chunk_gain_a = gain_a + (gain_b - gain_a) * chunk_start
            chunk_gain_b = gain_a + (gain_b - gain_a) * chunk_end
            events, timing = build_events(
                section_chunk,
                start_bpm=chunk_bpm_a,
                end_bpm=chunk_bpm_b,
                start_gain_db=chunk_gain_a,
                end_gain_db=chunk_gain_b,
                beatgrid_cache=beatgrid_cache,
            )
            events = cap_to_12(events)
            duration = max(event.timeline_end_s for event in events)
            musical_duration_s = len(section_chunk) * timing["body_s"]
            sample_points = [i * 4.0 for i in range(math.ceil(duration / 4.0))]
            active_counts = [active_count(events, point) for point in sample_points]
            part_path = args.out_dir / f"{chunk_name}.mp3"
            print(
                f"Rendering {chunk_name}: {len(section_chunk)} tracks, "
                f"{len(events)} stem events, max_active={max(active_counts)} -> {part_path}"
            )
            render(events, part_path, duration_s=musical_duration_s)
            rendered_parts += 1
            part_paths.append(part_path)
            all_events.extend(events)
            all_active_counts.extend(active_counts)
            section_manifests.append(
                {
                    "name": chunk_name,
                    "parent_section": name,
                    "timing": timing,
                    "musical_duration_s": musical_duration_s,
                    "part_path": str(part_path),
                    "track_order": [asdict(track) for track in section_chunk],
                    "event_count": len(events),
                    "max_active_events": max(active_counts),
                    "mean_active_events": sum(active_counts) / len(active_counts),
                }
            )
        if args.max_parts is not None and rendered_parts >= args.max_parts:
            break

    out_path = args.out_dir / "NINA_LIEBING_12DECK_PERFORMANCE_MATRIX.mp3"
    print(f"Joining sections -> {out_path}")
    join_parts(part_paths, out_path)
    scan = scan_mix(str(out_path))
    manifest = {
        "title": "Nina Kraviz x Chris Liebing 12-deck prepared-stem performance matrix",
        "source": str(args.stems_dir),
        "stem_order": list(STEM_ORDER),
        "track_order": [asdict(track) for track in order],
        "sections": section_manifests,
        "event_count": len(all_events),
        "max_active_events": max(all_active_counts),
        "mean_active_events": sum(all_active_counts) / len(all_active_counts),
        "drum_beatgrid": beatgrid_cache,
        "final_mix": {
            "path": str(out_path),
            "duration_s": scan.duration_s,
            "true_peak_db": scan.true_peak_db,
            "level_jumps": len(scan.level_jumps),
            "near_silent_s": len(scan.near_silent_s),
        },
        "events": [asdict(event) for event in all_events],
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)
    )
    print(json.dumps(manifest["final_mix"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
