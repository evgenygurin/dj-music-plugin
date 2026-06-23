#!/usr/bin/env python3
"""Continuous L5 (ADVANCED) sweep over the whole library — VM batch job.

Downloads each not-yet-L5 track to a temp file, runs the full L5 analyzer
set (essentia P3 DSP: danceability, dissonance, tonnetz, pitch_salience,
...), upserts the features at analysis_level=5, deletes the temp file.

Resumable: only touches tracks with analysis_level IS NULL or < 5, so a
restart picks up where it left off. Idempotent per track.

Run on the VM:
    PYTHONUNBUFFERED=1 uv run python -u scripts/vm_l5_sweep.py \
        --workers 8 --batch 200 2>&1 | tee -a /var/log/dj_l5.log

Flags:
    --workers N   concurrent track pipelines (default: cpu_count)
    --batch N     DB page size when pulling pending track_ids (default 200)
    --limit N     stop after N tracks (default: all)
    --min-level L only (re)do tracks below L (default 5)
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import sys
import time

from sqlalchemy import or_, select

from app.audio.analyzers import AnalyzerRegistry
from app.audio.level_config import AnalysisLevel, get_analyzers_for_level
from app.audio.pipeline import AnalysisPipeline
from app.audio.temp_download import temp_download_track
from app.config import get_settings
from app.db.session import dispose, get_session_factory
from app.models.track_features import TrackAudioFeaturesComputed as TF  # noqa: N814
from app.providers.yandex.client import YandexClient
from app.providers.yandex.rate_limiter import TokenBucketRateLimiter
from app.repositories.unit_of_work import UnitOfWork

# ── logging: real-time, per-task, noisy libs silenced ──────────────
with contextlib.suppress(Exception):
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
for noisy in ("httpx", "httpcore", "urllib3", "asyncio"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("l5")

L5_ANALYZERS = get_analyzers_for_level(AnalysisLevel.ADVANCED)


def _warmup_jit() -> None:
    """Prewarm numba/librosa JIT on the main thread before parallel dispatch.

    Without this, worker threads racing the lazy loader hit SEGV / scipy
    races (see .claude/rules/audio.md). ~3s, runs once.
    """
    try:
        import librosa
        import numpy as np

        sr = 22050
        y = np.random.RandomState(42).randn(sr * 5).astype(np.float32) * 0.1
        librosa.onset.onset_strength(y=y, sr=sr)
        librosa.beat.beat_track(y=y, sr=sr)
        librosa.feature.chroma_cqt(y=y, sr=sr)
        librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        librosa.feature.spectral_centroid(y=y, sr=sr)
        log.info("librosa/numba JIT warmed")
    except Exception as e:  # pragma: no cover
        log.warning("JIT warmup skipped: %s", e)


async def _pending_ids(session_factory, min_level: int, limit: int | None) -> list[int]:
    async with session_factory() as session:
        stmt = (
            select(TF.track_id)
            .where(or_(TF.analysis_level.is_(None), TF.analysis_level < min_level))
            .order_by(TF.track_id)
        )
        if limit:
            stmt = stmt.limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


async def _process_one(
    track_id: int,
    pipeline: AnalysisPipeline,
    client,
    session_factory,
    counters: dict,
    total: int,
    lock: asyncio.Lock,
) -> None:
    t0 = time.time()
    ok = False
    note = ""
    try:
        async with session_factory() as session:
            uow = UnitOfWork(session)
            # external_ids are stored under "yandex_music" (the download
            # handler tries both aliases — mirror that here).
            ext_id = await uow.tracks.get_provider_id(track_id, platform="yandex")
            if ext_id is None:
                ext_id = await uow.tracks.get_provider_id(track_id, platform="yandex_music")
            if ext_id is None:
                note = "no yandex ext_id"
            else:
                async with temp_download_track(client, str(ext_id)) as path:
                    result = await pipeline.analyze(str(path), analyzers=L5_ANALYZERS)
                feats = TF.filter_features(result.features)
                await uow.track_features.upsert(
                    track_id=track_id, analysis_level=int(AnalysisLevel.ADVANCED), **feats
                )
                await session.commit()
                ok = True
                note = f"{len(feats)} feats"
    except Exception as e:  # one bad track must not kill the sweep
        note = f"ERROR {type(e).__name__}: {e}"[:160]
    finally:
        async with lock:
            counters["done"] += 1
            counters["ok" if ok else "fail"] += 1
            log.info(
                "[%d/%d] track=%s %s in %.1fs (ok=%d fail=%d) %s",
                counters["done"],
                total,
                track_id,
                "OK" if ok else "SKIP/FAIL",
                time.time() - t0,
                counters["ok"],
                counters["fail"],
                note,
            )


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--batch", type=int, default=200)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--min-level", type=int, default=int(AnalysisLevel.ADVANCED))
    args = ap.parse_args()

    import os

    workers = args.workers or max(2, (os.cpu_count() or 4))
    _warmup_jit()

    registry = AnalyzerRegistry()
    registry.discover()
    avail = [n for n in L5_ANALYZERS if (a := registry.get(n)) and a.is_available()]
    log.info("L5 analyzers available: %d/%d → %s", len(avail), len(L5_ANALYZERS), avail)
    # use_processes=False: thread dispatch; we get parallelism across TRACKS
    # via the worker pool below, and librosa releases the GIL in C.
    pipeline = AnalysisPipeline(registry, use_processes=False)

    settings = get_settings()
    client = YandexClient(
        token=settings.yandex.token,
        user_id=str(settings.yandex.user_id),
        base_url=settings.yandex.base_url,
        rate_limiter=TokenBucketRateLimiter(delay_s=settings.yandex.rate_limit_delay_s),
    )

    session_factory = get_session_factory()
    pending = await _pending_ids(session_factory, args.min_level, args.limit or None)
    total = len(pending)
    log.info("pending L5: %d tracks, %d workers", total, workers)
    if not total:
        log.info("nothing to do — library already at L%d", args.min_level)
        await dispose()
        return

    counters = {"done": 0, "ok": 0, "fail": 0}
    lock = asyncio.Lock()
    sem = asyncio.Semaphore(workers)

    async def _guarded(tid: int) -> None:
        async with sem:
            await _process_one(tid, pipeline, client, session_factory, counters, total, lock)

    t0 = time.time()
    await asyncio.gather(*(_guarded(tid) for tid in pending))
    dt = time.time() - t0
    log.info(
        "DONE: %d ok, %d fail in %.0fs (%.1fs/track avg)",
        counters["ok"],
        counters["fail"],
        dt,
        dt / max(1, total),
    )
    await dispose()


if __name__ == "__main__":
    asyncio.run(main())
