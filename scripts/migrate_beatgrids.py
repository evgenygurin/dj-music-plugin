#!/usr/bin/env python3
"""Migrate first_downbeat_ms for all tracks with BPM but no beatgrid data.

Downloads first 5 seconds of each track from YM, detects first onset,
and saves first_downbeat_ms to track_audio_features_computed.

Usage:
    python scripts/migrate_beatgrids.py [--batch 200] [--workers 8] [--dry-run]
    python scripts/migrate_beatgrids.py --test-one  # single track test
"""

from __future__ import annotations

import argparse
import asyncio

# Force line-buffered output for real-time tail -F
import contextlib
import io
import logging
import sys
import time
from typing import Any

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("beatgrid-migrate")


def detect_first_downbeat_ms(
    audio_bytes: bytes,
    bpm: float,
    sr: int = 22050,
) -> float | None:
    """Detect the first downbeat position from raw audio bytes.

    Uses onset strength to find the first strong transient, then snaps
    it to the nearest beat grid position derived from BPM.
    """
    try:
        import librosa
        import soundfile as sf
    except ImportError:
        log.error("librosa/soundfile not installed — run: uv sync --extra audio")
        return None

    # Decode audio from bytes
    try:
        y, actual_sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    except Exception:
        return None

    if y.ndim > 1:
        y = y.mean(axis=1)

    if actual_sr != sr:
        y = librosa.resample(y, orig_sr=actual_sr, target_sr=sr)

    if len(y) < sr:  # less than 1 second
        return None

    # Detect onsets in first 5 seconds
    clip = y[: sr * 5]
    onset_env = librosa.onset.onset_strength(y=clip, sr=sr)
    onsets = librosa.onset.onset_detect(
        y=clip, sr=sr, onset_envelope=onset_env, units="time", backtrack=True
    )

    if len(onsets) == 0:
        return 0.0  # no onsets detected, assume start

    # First strong onset
    first_onset_sec = float(onsets[0])

    # Snap to nearest beat grid position
    beat_interval = 60.0 / bpm  # seconds per beat
    beat_interval * 4  # seconds per bar (4/4)

    # The first downbeat is the nearest grid position to the first onset
    # that makes musical sense (within half a beat of the onset)
    grid_pos = round(first_onset_sec / beat_interval) * beat_interval

    # If grid_pos is more than half a beat away, use raw onset
    if abs(grid_pos - first_onset_sec) > beat_interval / 2:
        grid_pos = first_onset_sec

    return grid_pos * 1000.0  # convert to ms


async def get_tracks_needing_beatgrid(session: Any) -> list[dict[str, Any]]:
    """Fetch tracks with BPM but no first_downbeat_ms."""
    from sqlalchemy import text

    result = await session.execute(
        text("""
            SELECT f.track_id, f.bpm, e.external_id AS ym_track_id
            FROM track_audio_features_computed f
            JOIN track_external_ids e ON e.track_id = f.track_id AND e.platform = 'yandex_music'
            WHERE f.bpm IS NOT NULL
              AND f.first_downbeat_ms IS NULL
            ORDER BY f.track_id
        """)
    )
    return [{"track_id": r[0], "bpm": r[1], "ym_track_id": r[2]} for r in result.fetchall()]


async def download_audio_clip(
    ym_client: Any, ym_track_id: str, max_bytes: int = 200_000
) -> bytes | None:
    """Download first ~5 seconds of audio from YM (partial Range request)."""
    try:
        # Get download info
        info = await ym_client.get_download_info(ym_track_id)
        if not info:
            return None

        # Pick highest bitrate
        best = max(info, key=lambda x: x.get("bitrateInKbps", 0))
        url = best.get("url") or best.get("directUrl")
        if not url:
            # Build URL from codec/bitrate info
            url = await ym_client.build_download_url(best)
        if not url:
            return None

        # Range request: first max_bytes (~5 sec at 320kbps ≈ 200KB)
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(url, headers={"Range": f"bytes=0-{max_bytes}"})
            if resp.status_code in (200, 206):
                return resp.content
            return None
    except Exception as e:
        log.debug("Download failed for %s: %s", ym_track_id, e)
        return None


async def process_batch(
    session: Any,
    ym_client: Any,
    tracks: list[dict[str, Any]],
    workers: int,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Process a batch of tracks. Returns (success, failed)."""
    from sqlalchemy import text

    sem = asyncio.Semaphore(workers)
    counters = {"ok": 0, "fail": 0, "done": 0}
    lock = asyncio.Lock()
    total = len(tracks)

    async def _process_one(track: dict[str, Any]) -> None:
        async with sem:
            t0 = time.time()
            track_id = track["track_id"]
            ym_id = track["ym_track_id"]
            bpm = track["bpm"]

            audio = await download_audio_clip(ym_client, str(ym_id))
            if audio is None:
                async with lock:
                    counters["done"] += 1
                    counters["fail"] += 1
                    log.info(
                        "    [%d/%d] track=%d ym=%s FAIL (download) in %.1fs",
                        counters["done"],
                        total,
                        track_id,
                        ym_id,
                        time.time() - t0,
                    )
                return

            downbeat_ms = detect_first_downbeat_ms(audio, bpm)
            if downbeat_ms is None:
                async with lock:
                    counters["done"] += 1
                    counters["fail"] += 1
                    log.info(
                        "    [%d/%d] track=%d ym=%s FAIL (detect) in %.1fs",
                        counters["done"],
                        total,
                        track_id,
                        ym_id,
                        time.time() - t0,
                    )
                return

            if not dry_run:
                await session.execute(
                    text(
                        "UPDATE track_audio_features_computed "
                        "SET first_downbeat_ms = :val WHERE track_id = :tid"
                    ),
                    {"val": round(downbeat_ms, 2), "tid": track_id},
                )

            async with lock:
                counters["done"] += 1
                counters["ok"] += 1
                if counters["done"] % 50 == 0 or counters["done"] == total:
                    log.info(
                        "    [%d/%d] track=%d downbeat=%.1fms in %.1fs (ok=%d fail=%d)",
                        counters["done"],
                        total,
                        track_id,
                        downbeat_ms,
                        time.time() - t0,
                        counters["ok"],
                        counters["fail"],
                    )

    tasks = [_process_one(t) for t in tracks]
    await asyncio.gather(*tasks, return_exceptions=True)

    if not dry_run:
        await session.commit()

    return counters["ok"], counters["fail"]


async def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate first_downbeat_ms for all tracks")
    parser.add_argument("--batch", type=int, default=200, help="Batch size for commits")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent downloads")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    parser.add_argument("--test-one", action="store_true", help="Process one track and exit")
    args = parser.parse_args()

    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import settings

    engine = create_async_engine(
        settings.database_url,
        connect_args={"statement_cache_size": 0},  # PgBouncer compat
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Initialize YM client
    from app.ym.client import YandexMusicClient

    ym = YandexMusicClient()

    async with async_session() as session:
        tracks = await get_tracks_needing_beatgrid(session)
        log.info("Found %d tracks needing beatgrid migration", len(tracks))

        if not tracks:
            log.info("Nothing to migrate!")
            await engine.dispose()
            return

        if args.test_one:
            tracks = tracks[:1]
            log.info("Test mode: processing 1 track")

        total_ok, total_fail = 0, 0
        for i in range(0, len(tracks), args.batch):
            batch = tracks[i : i + args.batch]
            log.info(
                "=== Batch %d/%d (%d tracks) ===",
                i // args.batch + 1,
                (len(tracks) + args.batch - 1) // args.batch,
                len(batch),
            )
            ok, fail = await process_batch(session, ym, batch, args.workers, args.dry_run)
            total_ok += ok
            total_fail += fail

        log.info("=== DONE: ok=%d fail=%d total=%d ===", total_ok, total_fail, len(tracks))

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
