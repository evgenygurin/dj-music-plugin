#!/usr/bin/env python3
"""Continuous Beatport genre backfill over the whole library — VM batch job.

For every track without a Beatport verdict yet, match it on Beatport
(title+artist, BPM/duration-verified via the real provider adapter) and persist
the human-curated genre into the ``beatport_*`` columns of
``track_audio_features_computed``.

Resumable + idempotent: a track is "done" once ``beatport_confidence`` is set
— ``high``/``medium`` for a match (genre populated), or the sentinel ``none``
for an attempted-but-unmatched track. A restart only revisits rows where
``beatport_confidence IS NULL``, so no track is searched twice.

Network-bound (Beatport rate-limited), so it co-exists with the CPU-bound L5
sweep without contention. Writes only the ``beatport_*`` columns, so it never
clobbers features the L5 sweep is upserting concurrently.

Run on the VM:
    PYTHONUNBUFFERED=1 uv run python -u scripts/vm_beatport_backfill.py \
        --workers 6 2>&1 | tee -a /var/log/dj_beatport.log

Flags:
    --workers N   concurrent match tasks (default 6; Beatport rate-limiter caps
                  actual throughput regardless)
    --batch N     DB page size when pulling pending track ids (default 500)
    --limit N     stop after N tracks (default: all)
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import sys
import time

from sqlalchemy import select

from app.db.session import dispose, get_session_factory
from app.models.track import Track
from app.models.track_features import TrackAudioFeaturesComputed as TF  # noqa: N814
from app.repositories.unit_of_work import UnitOfWork
from app.server.lifespan import build_beatport_adapter

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
for noisy in ("httpx", "httpcore", "urllib3", "asyncio"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("bp")


def _split_artist_title(title: str | None) -> tuple[str, str]:
    raw = (title or "").strip()
    if " - " in raw:
        artist, _, t = raw.partition(" - ")
        return artist.strip(), t.strip()
    return "", raw


async def _pending(
    session_factory, limit: int | None
) -> list[tuple[int, str | None, float | None, int | None]]:
    async with session_factory() as session:
        stmt = (
            select(TF.track_id, Track.title, TF.bpm, Track.duration_ms)
            .join(Track, Track.id == TF.track_id)
            .where(TF.beatport_confidence.is_(None))
            .order_by(TF.track_id)
        )
        if limit:
            stmt = stmt.limit(limit)
        rows = (await session.execute(stmt)).all()
    return [(r[0], r[1], r[2], r[3]) for r in rows]


async def _process_one(
    row: tuple[int, str | None, float | None, int | None],
    adapter,
    session_factory,
    counters: dict,
    total: int,
    lock: asyncio.Lock,
) -> None:
    track_id, title, bpm, duration_ms = row
    t0 = time.time()
    status = "FAIL"
    note = ""
    try:
        artist, ttl = _split_artist_title(title)
        if not artist and ttl:
            # Title has no "Artist - " prefix — fall back to the artists
            # relation so e.g. "Jilted" by Spektre still matches.
            async with session_factory() as s:
                artist = await UnitOfWork(s).tracks.get_primary_artist_name(track_id) or ""
        if not ttl:
            verdict = {"matched": False, "confidence": "none"}
        else:
            params: dict = {"artist": artist, "title": ttl}
            if bpm is not None:
                params["bpm"] = float(bpm)
            if duration_ms is not None:
                params["duration_ms"] = int(duration_ms)
            verdict = await adapter.read("track_match", None, params)

        async with session_factory() as session:
            uow = UnitOfWork(session)
            if verdict.get("matched"):
                await uow.track_features.upsert(
                    track_id=track_id,
                    beatport_genre=verdict.get("genre"),
                    beatport_sub_genre=verdict.get("sub_genre"),
                    beatport_track_id=verdict.get("beatport_id"),
                    beatport_confidence=verdict.get("confidence"),
                )
                status = "MATCH"
                note = f"{verdict.get('confidence')} {verdict.get('genre')}"
            else:
                # Sentinel so a restart never re-searches this track.
                await uow.track_features.upsert(track_id=track_id, beatport_confidence="none")
                status = "NONE"
                note = f"no match ({verdict.get('confidence')})"
            await session.commit()
    except Exception as e:  # one bad track must not kill the backfill
        note = f"ERROR {type(e).__name__}: {e}"[:160]
    finally:
        async with lock:
            counters["done"] += 1
            if status == "MATCH":
                counters["match"] += 1
            elif status == "NONE":
                counters["none"] += 1
            else:
                counters["fail"] += 1
            log.info(
                "[%d/%d] track=%s %s in %.1fs (match=%d none=%d fail=%d) %s",
                counters["done"],
                total,
                track_id,
                status,
                time.time() - t0,
                counters["match"],
                counters["none"],
                counters["fail"],
                note,
            )


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--batch", type=int, default=500)  # reserved; full pull today
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    adapter = build_beatport_adapter()
    if adapter is None:
        log.error("Beatport adapter unavailable — set DJ_BEATPORT_USERNAME/PASSWORD in .env")
        return

    session_factory = get_session_factory()
    pending = await _pending(session_factory, args.limit or None)
    total = len(pending)
    log.info("pending Beatport backfill: %d tracks, %d workers", total, args.workers)
    if not total:
        log.info("nothing to do — every track already has a beatport verdict")
        await adapter.close()
        await dispose()
        return

    counters = {"done": 0, "match": 0, "none": 0, "fail": 0}
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(args.workers)

    async def _guarded(row) -> None:
        async with sem:
            await _process_one(row, adapter, session_factory, counters, total, lock)

    t0 = time.time()
    try:
        await asyncio.gather(*(_guarded(r) for r in pending))
    finally:
        await adapter.close()
    dt = time.time() - t0
    log.info(
        "DONE: %d match, %d none, %d fail in %.0fs (%.2fs/track avg)",
        counters["match"],
        counters["none"],
        counters["fail"],
        dt,
        dt / max(1, total),
    )
    await dispose()


if __name__ == "__main__":
    asyncio.run(main())
