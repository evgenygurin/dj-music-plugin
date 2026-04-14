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

import numpy as np

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
    """Detect the beat grid phase (first downbeat offset) from audio.

    Strategy (autocorrelation-based, not first-onset):
      1. Decode audio, skip first 2 seconds (MP3 padding + possible silence)
      2. Compute energy envelope in short frames
      3. Build an autocorrelation at the expected beat interval
      4. Find the phase offset where kicks align best
      5. Extrapolate back to get the first downbeat position from sample 0

    This gives the PHASE of the beat grid, not the position of the
    first audible transient — which is what crossfade alignment needs.
    """
    try:
        import soundfile as sf
    except ImportError:
        log.error("soundfile not installed — run: uv sync --extra audio")
        return None

    try:
        # Suppress libsndfile "Xing stream size off" C-level warning
        # from partial MP3 Range downloads (stderr redirect)
        import os

        devnull = os.open(os.devnull, os.O_WRONLY)
        old_stderr = os.dup(2)
        os.dup2(devnull, 2)
        try:
            y, actual_sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        finally:
            os.dup2(old_stderr, 2)
            os.close(devnull)
            os.close(old_stderr)
    except Exception:
        return None

    if y.ndim > 1:
        y = y.mean(axis=1)

    # Resample to target sr by decimation
    if actual_sr != sr:
        ratio = actual_sr / sr
        indices = np.arange(0, len(y), ratio).astype(int)
        indices = indices[indices < len(y)]
        y = y[indices]

    duration = len(y) / sr
    if duration < 3.0:
        return None

    # --- Step 1: Find a "loud" region (skip silence/intro) ---
    # Use the loudest 4-second window for beat phase detection.
    # This avoids MP3 padding, fade-ins, and ambient intros.
    hop = 256
    n_frames = len(y) // hop
    frame_energy = np.array([np.sum(y[i * hop : (i + 1) * hop] ** 2) for i in range(n_frames)])

    # Sliding window RMS over 4 seconds
    win_frames = int(4.0 * sr / hop)
    if win_frames >= n_frames:
        win_frames = n_frames - 1
    cum = np.cumsum(frame_energy)
    win_sums = cum[win_frames:] - cum[:-win_frames]
    best_start_frame = int(np.argmax(win_sums))
    analysis_start = best_start_frame * hop
    analysis_end = min(len(y), analysis_start + int(4.0 * sr))
    clip = y[analysis_start:analysis_end]

    if len(clip) < sr * 2:
        return 0.0

    # --- Step 2: Compute per-sample energy envelope (rectify + smooth) ---
    rect = np.abs(clip)
    # Smooth with a ~5ms window for kick detection
    smooth_len = max(1, int(0.005 * sr))
    kernel = np.ones(smooth_len) / smooth_len
    env = np.convolve(rect, kernel, mode="same")

    # --- Step 3: Find beat phase via template matching ---
    # Create a comb template at BPM interval and slide it across
    # one beat period to find the offset that maximizes correlation.
    beat_samples = int(60.0 / bpm * sr)
    if beat_samples < 10 or beat_samples >= len(env):
        return 0.0

    # Number of beats that fit in the clip
    n_beats = len(env) // beat_samples
    if n_beats < 3:
        return 0.0

    # For each candidate phase (0..beat_samples), sum energy at
    # all beat positions. The phase with highest sum = the grid offset.
    # This is equivalent to folding the signal at beat period.
    usable = n_beats * beat_samples
    folded = env[:usable].reshape(n_beats, beat_samples)
    phase_profile = np.sum(folded, axis=0)

    # The peak of phase_profile = the within-beat offset where kicks land
    peak_offset_samples = int(np.argmax(phase_profile))

    # --- Step 4: Convert to absolute position and extrapolate to sample 0 ---
    # The detected phase is relative to analysis_start.
    # Absolute position of the nearest beat: analysis_start + peak_offset
    abs_phase_sample = analysis_start + peak_offset_samples

    # Extrapolate backwards to find the first beat at or after sample 0:
    # first_downbeat = abs_phase % beat_samples
    first_downbeat_sample = abs_phase_sample % beat_samples

    first_downbeat_ms = float(first_downbeat_sample) / sr * 1000.0

    # Sanity: must be within one beat interval
    beat_interval_ms = 60_000.0 / bpm
    if first_downbeat_ms >= beat_interval_ms:
        first_downbeat_ms = first_downbeat_ms % beat_interval_ms

    return round(first_downbeat_ms, 2)


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
    ym_client: Any,
    ym_track_id: str,
    max_bytes: int = 200_000,
    http_client: Any = None,
) -> bytes | None:
    """Download first ~5 seconds of audio from YM (partial Range request).

    Uses YM's two-step download: get_download_info → resolve URL → Range GET.
    At 320kbps, 200KB ≈ 5 seconds of audio.
    Uses a shared httpx client to avoid per-request connection overhead.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            infos = await ym_client.get_download_info(str(ym_track_id))
            if not infos:
                return None

            best = infos[0]
            download_info_url = best.get("downloadInfoUrl")
            if not download_info_url:
                return None

            download_url = await ym_client._resolve_download_url(
                str(ym_track_id), download_info_url
            )

            client = http_client
            if client is None:
                import httpx

                client = httpx.AsyncClient(timeout=15.0)
            resp = await client.get(download_url, headers={"Range": f"bytes=0-{max_bytes}"})
            if resp.status_code in (200, 206):
                return resp.content
            return None
        except Exception as e:
            err_str = str(e)
            is_rate_limit = "Rate limited" in err_str or "429" in err_str
            is_no_rights = "no-rights" in err_str or "403" in err_str
            if is_no_rights:
                return None  # permanent, no retry
            if is_rate_limit and attempt < max_retries - 1:
                wait = 2.0 * (attempt + 1)  # 2s, 4s
                await asyncio.sleep(wait)
                continue
            if attempt == max_retries - 1:
                log.warning(
                    "Download failed for ym=%s after %d attempts: %s", ym_track_id, max_retries, e
                )
            return None
    return None


async def process_batch(
    session: Any,
    ym_client: Any,
    tracks: list[dict[str, Any]],
    workers: int,
    dry_run: bool = False,
    http_client: Any = None,
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

            audio = await download_audio_clip(ym_client, str(ym_id), http_client=http_client)
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

            # Serialize DB writes behind lock — asyncpg connection state
            # machine is not safe for concurrent commands on one session.
            async with lock:
                if not dry_run:
                    await session.execute(
                        text(
                            "UPDATE track_audio_features_computed "
                            "SET first_downbeat_ms = :val WHERE track_id = :tid"
                        ),
                        {"val": round(downbeat_ms, 2), "tid": track_id},
                    )

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
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Surface unexpected exceptions that slipped past per-track handling
    for idx, res in enumerate(results):
        if isinstance(res, BaseException):
            track_id = tracks[idx]["track_id"]
            log.error("    Unexpected error for track=%d: %s", track_id, res)
            counters["fail"] += 1

    if not dry_run:
        await session.commit()

    return counters["ok"], counters["fail"]


async def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate first_downbeat_ms for all tracks")
    parser.add_argument("--batch", type=int, default=200, help="Batch size for commits")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent downloads")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    parser.add_argument("--test-one", action="store_true", help="Process one track and exit")
    parser.add_argument(
        "--delay", type=float, default=0.2, help="YM rate limiter delay in seconds"
    )
    args = parser.parse_args()

    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from app.config import settings

    # Use direct connection (port 5432) instead of PgBouncer (6543)
    # to avoid prepared statement and search_path issues.
    db_url = settings.database_url.replace(":6543/", ":5432/")
    engine = create_async_engine(
        db_url,
        connect_args={"statement_cache_size": 0},
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Initialize YM client with settings
    from app.clients.ym.client import YandexMusicClient
    from app.clients.ym.rate_limiter import RateLimiter

    ym = YandexMusicClient(
        token=settings.ym_token,
        user_id=settings.ym_user_id,
        base_url=settings.ym_base_url,
        rate_limiter=RateLimiter(delay=args.delay),
    )
    log.info("YM rate limiter delay: %.2fs", args.delay)

    import httpx

    async with httpx.AsyncClient(timeout=15.0) as shared_http, async_session() as session:
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
            ok, fail = await process_batch(
                session, ym, batch, args.workers, args.dry_run, http_client=shared_http
            )
            total_ok += ok
            total_fail += fail

        log.info("=== DONE: ok=%d fail=%d total=%d ===", total_ok, total_fail, len(tracks))

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
