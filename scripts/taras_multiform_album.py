#!/usr/bin/env python3
"""Generate Taras multiform album in Suno and write local manifest."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from app.domain.suno_voice.taras_album import (
    TARAS_ALBUM_TITLE,
    TARAS_ALBUM_TRACKS,
    assemble_taras_album_prompt,
)
from app.providers.suno.client_errors import AuthFailedError
from app.server.lifespan import build_suno_adapter

OUT = Path("suno_out/taras_album")


async def poll(adapter: object, clip_id: str, timeout_s: float = 240) -> dict:
    deadline = time.monotonic() + timeout_s
    last = {}
    while time.monotonic() < deadline:
        last = await adapter.read(entity="generation", id=clip_id, params={})
        if last.get("audio_url"):
            return last
        await asyncio.sleep(4)
    return last


async def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    adapter = build_suno_adapter()
    if adapter is None:
        print("Suno adapter disabled")
        return 2
    try:
        await adapter.read(entity="account", id=None, params={})
    except AuthFailedError:
        print(
            "Suno session auth expired or challenge required. "
            "Refresh token / open browser challenge and rerun."
        )
        return 3

    results = []
    for track_def in TARAS_ALBUM_TRACKS:
        track, style, negative = assemble_taras_album_prompt(track_def.slug)
        try:
            created = await adapter.write(
                entity="generation",
                operation="create",
                params={
                    "title": track.title,
                    "prompt": track.lyrics,
                    "lyrics": track.lyrics,
                    "tags": style,
                    "style": style,
                    "negative_tags": negative,
                    "instrumental": False,
                    "model": "chirp-fenix",
                },
            )
        except AuthFailedError:
            print("Suno requires CAPTCHA/challenge for this account or IP.")
            print("Complete it in the browser, then rerun:")
            print("uv run python scripts/taras_multiform_album.py")
            return 5
        clip_ids = list(created.get("clip_ids") or [])
        if not clip_ids and created.get("generation_id"):
            clip_ids = [created["generation_id"]]
        clips = []
        for cid in clip_ids[:2]:
            cid = str(cid)
            clip = await poll(adapter, cid)
            row = {"clip_id": cid, "suno_url": f"https://suno.com/song/{cid}"}
            if clip.get("audio_url"):
                row["audio_url"] = clip["audio_url"]
                row["duration"] = (
                    (clip.get("raw") or {}).get("metadata", {}).get("duration")
                    if isinstance(clip.get("raw"), dict)
                    else None
                )
                dl = await adapter.write(
                    entity="generation",
                    operation="download",
                    params={
                        "generation_id": cid,
                        "target_dir": str(OUT),
                        "title": f"{track.slug}_{cid[:8]}",
                        "audio_url": clip["audio_url"],
                    },
                )
                row["local_path"] = dl.get("file_path") or dl.get("path") or dl.get("local_path")
            clips.append(row)
        results.append({
            "slug": track.slug,
            "title": track.title,
            "style": style,
            "lyrics": track.lyrics,
            "clips": clips,
        })

    playlist = None
    try:
        playlist = await adapter.write(
            entity="playlist",
            operation="create",
            params={"name": TARAS_ALBUM_TITLE},
        )
        playlist_id = playlist.get("playlist_id") or playlist.get("id")
        first_clip_ids = [item["clips"][0]["clip_id"] for item in results if item.get("clips")]
        if playlist_id and first_clip_ids:
            await adapter.write(
                entity="playlist",
                operation="add_tracks",
                params={"playlist_id": playlist_id, "clip_ids": first_clip_ids},
            )
    except Exception as exc:  # best-effort album container
        playlist = {"warning": str(exc)}

    summary = {"album_title": TARAS_ALBUM_TITLE, "playlist": playlist, "tracks": results}
    (OUT / "SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = [f"# {TARAS_ALBUM_TITLE}", "", "| Track | Suno | Local | Duration |", "|---|---|---|---|"]
    for item in results:
        first = item["clips"][0] if item["clips"] else {}
        local_name = Path(first["local_path"]).name if first.get("local_path") else "-"
        duration = first.get("duration") or "-"
        md.append(
            f"| {item['title']} | [clip]({first.get('suno_url','')}) | {local_name} | {duration} |"
        )
    (OUT / "LISTEN.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
