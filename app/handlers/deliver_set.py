"""Handler: build a deliverable bundle for a set version."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any
from xml.sax.saxutils import quoteattr

from app.config import get_settings
from app.handlers._context_log import safe_info
from app.schemas.delivery import DeliverSetResult
from app.shared.workspace import render_workspace

_CAMELOT_TO_KEY: dict[str, str] = {
    "7A": "Dm",
    "7B": "F",
    "8A": "Am",
    "8B": "C",
    "9A": "Em",
    "9B": "G",
    "10A": "Bm",
    "10B": "D",
    "11A": "F#m",
    "11B": "A",
    "12A": "C#m",
    "12B": "E",
    "1A": "Ebm",
    "1B": "Gb",
    "2A": "Bbm",
    "2B": "Db",
    "3A": "Fm",
    "3B": "Ab",
    "4A": "Cm",
    "4B": "Eb",
    "5A": "Gm",
    "5B": "Bb",
    "6A": "Dm",
    "6B": "F",
}


def _safe_filename(s: str) -> str:
    return s.replace("/", "-")


def _is_real_file(path: Path, ratio: float) -> bool:
    try:
        stat = os.stat(path)
        return stat.st_blocks * 512 >= stat.st_size * ratio
    except OSError:
        return False


def _camelot_str(key_code: int | None) -> str:
    if key_code is None:
        return ""
    return f"{key_code % 12 + 1}{'B' if key_code >= 12 else 'A'}"


async def deliver_set_handler(
    *, ctx: Any, uow: Any, version_id: int, out_dir: str | None = None
) -> DeliverSetResult:
    s = get_settings()
    d = s.delivery

    if out_dir is None:
        out_dir = str(Path(d.output_dir) / "deliver" / f"v{version_id}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    inputs = await uow.set_versions.get_render_inputs(version_id)
    ws = render_workspace(version_id)

    files: list[str] = []

    if d.copy_audio_files:
        tracks_dir = out / "tracks"
        tracks_dir.mkdir(exist_ok=True)
        for k, ti in enumerate(inputs, 1):
            src = Path(ti.file_path)
            if not src.exists():
                continue
            if not _is_real_file(src, d.icloud_min_download_ratio):
                continue
            dst_name = f"{k:02d}_{_safe_filename(ti.title)}.mp3"
            shutil.copy2(str(src), str(tracks_dir / dst_name))
            files.append(f"tracks/{dst_name}")

    if d.emit_m3u8:
        m3u_lines = ["#EXTM3U", f"#PLAYLIST:version {version_id}"]
        for k, ti in enumerate(inputs, 1):
            m3u_lines.append(f"#EXTINF:0,{ti.title}")
            m3u_lines.append(f"tracks/{k:02d}_{_safe_filename(ti.title)}.mp3")
        (out / "playlist.m3u8").write_text("\n".join(m3u_lines) + "\n")
        files.append("playlist.m3u8")

    if d.emit_rekordbox_xml:
        n = len(inputs)
        coll_lines = [f'  <COLLECTION Entries="{n}">']
        for k, ti in enumerate(inputs, 1):
            artist, _, name = ti.title.partition(" - ")
            cam_str = _camelot_str(ti.key_code)
            tonality = _CAMELOT_TO_KEY.get(cam_str, "")
            loc = "file://localhost" + str(
                (out / "tracks" / f"{k:02d}_{_safe_filename(ti.title)}.mp3").resolve()
            )
            coll_lines.append(
                f'    <TRACK TrackID="{k}" Name={quoteattr(name or ti.title)} '
                f'Artist={quoteattr(artist)} Kind="MP3 File" AverageBpm="{ti.bpm:.2f}" '
                f"Tonality={quoteattr(tonality)} Location={quoteattr(loc)}/>"
            )
        coll_lines.append("  </COLLECTION>")
        (out / "rekordbox.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<DJ_PLAYLISTS>\n'
            + "\n".join(coll_lines)
            + "\n</DJ_PLAYLISTS>\n"
        )
        files.append("rekordbox.xml")

    if d.emit_json_guide:
        rows = [
            {
                "index": k,
                "title": ti.title,
                "bpm": ti.bpm,
                "key_code": ti.key_code,
            }
            for k, ti in enumerate(inputs, 1)
        ]
        (out / "guide.json").write_text(__import__("json").dumps(rows, indent=1))
        files.append("guide.json")

    if d.emit_cheatsheet:
        lines = [f"Set version: {version_id}", ""]
        for k, ti in enumerate(inputs, 1):
            cam_str = _camelot_str(ti.key_code)
            tonality = _CAMELOT_TO_KEY.get(cam_str, "")
            lines.append(f"{k:02d}. {ti.title} [{ti.bpm:.0f} BPM / {tonality}]")
        (out / "cheatsheet.txt").write_text("\n".join(lines) + "\n")
        files.append("cheatsheet.txt")

    if ws and d.emit_continuous_mix:
        mix = Path(ws) / "MIX.mp3"
        if mix.exists():
            shutil.copy2(str(mix), str(out / "MIX.mp3"))
            files.append("MIX.mp3")

    if ctx is not None:
        await safe_info(ctx, f"deliver_set: v{version_id} -> {out} ({len(files)} files)")

    return DeliverSetResult(
        version_id=version_id,
        out_dir=str(out),
        files=files,
        track_count=len(inputs),
        m3u8=d.emit_m3u8,
        rekordbox_xml=d.emit_rekordbox_xml,
        json_guide=d.emit_json_guide,
        cheatsheet=d.emit_cheatsheet,
        continuous_mix=ws and d.emit_continuous_mix and (Path(ws) / "MIX.mp3").exists(),
    )
