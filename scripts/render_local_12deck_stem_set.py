"""Render a local prepared-stem techno set without touching the DB.

This is a safe fallback for `/Users/laptop/Desktop/Stems`: it consumes the
already-separated files directly and never runs demucs or writes Supabase rows.

Run:
    PATH="/opt/homebrew/bin:$PATH" uv run python scripts/render_local_12deck_stem_set.py
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.audio.render.diagnostics import scan_mix
from app.audio.render.runner import run_render
from app.domain.render.models import STEM_ORDER, BeatgridEntry, TrackInput
from app.domain.render.timeline import build_stem_render_plan

STEMS_DIR = Path("/Users/laptop/Desktop/Stems")
OUT_DIR = Path("generated-sets/12deck-prepared-stems-2026-07-21")
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
class RenderSection:
    name: str
    target_bpm: float
    tracks: list[StemTrack]
    out_name: str


def parse_stems(stems_dir: Path) -> list[StemTrack]:
    by_index: dict[int, StemTrack] = {}
    for path in sorted(stems_dir.glob("*.m4a")):
        match = STEM_PATTERN.match(path.name)
        if match is None:
            continue
        idx = int(match.group("index"))
        track = by_index.setdefault(
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
    return [track for track in by_index.values() if required.issubset(track.stems)]


def _pick_arc(
    tracks: list[StemTrack],
    *,
    bpm_min: float,
    bpm_max: float,
    genres: set[str],
    count: int,
    ascending: bool = True,
) -> list[StemTrack]:
    pool = [
        track
        for track in tracks
        if bpm_min <= track.bpm <= bpm_max and track.genre in genres
    ]
    pool.sort(key=lambda track: (track.bpm, track.genre, track.index), reverse=not ascending)
    picked: list[StemTrack] = []
    seen_titles: set[str] = set()
    seen_genres: set[str] = set()
    for track in pool:
        key = track.title.lower()
        if key in seen_titles:
            continue
        if track.genre in seen_genres and len(seen_genres) < min(count, len(genres)):
            continue
        picked.append(track)
        seen_titles.add(key)
        seen_genres.add(track.genre)
        if len(picked) == count:
            return picked
    for track in pool:
        key = track.title.lower()
        if key in seen_titles:
            continue
        picked.append(track)
        seen_titles.add(key)
        if len(picked) == count:
            return picked
    return picked


def curate_sections(tracks: list[StemTrack]) -> list[RenderSection]:
    story1 = _pick_arc(
        tracks,
        bpm_min=126,
        bpm_max=130,
        genres={"hypnotic", "dub_techno", "detroit", "minimal", "progressive", "melodic_deep"},
        count=6,
    )
    bridge = _pick_arc(
        tracks,
        bpm_min=131,
        bpm_max=132,
        genres={"acid", "driving", "detroit", "industrial", "progressive", "peak_time"},
        count=2,
    )
    story2 = _pick_arc(
        tracks,
        bpm_min=133,
        bpm_max=140,
        genres={"industrial", "peak_time", "hard_techno", "acid", "driving"},
        count=6,
    )
    if len(story1) < 4 or len(story2) < 4:
        raise RuntimeError("Not enough tracks for the requested two-story arc")
    return [
        RenderSection("story1_nina_hypnotic", 128.0, story1, "PART_1_128BPM.mp3"),
        RenderSection("bridge_132", 132.0, bridge, "PART_2_BRIDGE_132BPM.mp3"),
        RenderSection("story2_liebing_peak", 136.0, story2, "PART_3_136BPM.mp3"),
    ]


def build_section_plan(section: RenderSection):
    inputs = [
        TrackInput(
            track_id=track.index,
            yandex_id=None,
            title=track.title,
            bpm=track.bpm,
            key_code=None,
            mix_in_ms=0,
            integrated_lufs=None,
            file_path=track.stems["instrumental"],
            duration_ms=None,
        )
        for track in section.tracks
    ]
    grid = {
        track.index: BeatgridEntry(
            track_id=track.index,
            trim_start_s=0.0,
            refined_trim_s=0.0,
            gain_db=0.0,
            phase_ms=0.0,
        )
        for track in section.tracks
    }
    stems = {track.index: track.stems for track in section.tracks}
    return build_stem_render_plan(
        inputs,
        stems,
        grid,
        target_bpm=section.target_bpm,
        body_bars=8,
        transition_bars=16,
        xsplit_low_hz=250,
        xsplit_high_hz=4000,
        eq_phase_1_ratio=0.40,
        eq_phase_2_ratio=0.70,
        low_swap_beats=1.0,
        outro_fade_bars=8,
        limiter_ceiling=0.88,
        bass_swap_ratio=0.72,
    )


def join_parts(parts: list[Path], out_path: Path) -> None:
    if len(parts) == 1:
        out_path.write_bytes(parts[0].read_bytes())
        return
    cmd = [
        "ffmpeg",
        "-y",
        *[arg for part in parts for arg in ("-i", str(part))],
        "-filter_complex",
        (
            "[0:a][1:a]acrossfade=d=12:c1=qsin:c2=qsin[x1];"
            "[x1][2:a]acrossfade=d=12:c1=qsin:c2=qsin,"
            "loudnorm=I=-14:LRA=6:TP=-1.0,"
            "alimiter=limit=0.88:attack=10:release=30[mix]"
        ),
        "-map",
        "[mix]",
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
        raise RuntimeError((proc.stderr or "")[-2000:])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stems-dir", type=Path, default=STEMS_DIR)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    tracks = parse_stems(args.stems_dir)
    sections = curate_sections(tracks)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    part_paths: list[Path] = []
    manifest: dict[str, object] = {
        "title": "Nina Kraviz x Chris Liebing prepared-stem 12-deck study",
        "source": str(args.stems_dir),
        "stem_order": list(STEM_ORDER),
        "sections": [],
    }
    for section in sections:
        out_path = args.out_dir / section.out_name
        print(f"Rendering {section.name} -> {out_path}")
        run_render(build_section_plan(section), str(out_path))
        part_paths.append(out_path)
        manifest["sections"].append(
            {
                "name": section.name,
                "target_bpm": section.target_bpm,
                "out_path": str(out_path),
                "tracks": [asdict(track) for track in section.tracks],
            }
        )

    final_path = args.out_dir / "NINA_LIEBING_PREPARED_STEMS_FINAL.mp3"
    print(f"Joining parts -> {final_path}")
    join_parts(part_paths, final_path)
    report = scan_mix(str(final_path))
    manifest["final_mix"] = {
        "path": str(final_path),
        "duration_s": report.duration_s,
        "true_peak_db": report.true_peak_db,
        "level_jumps": len(report.level_jumps),
        "near_silent_s": len(report.near_silent_s),
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)
    )
    print(json.dumps(manifest["final_mix"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
