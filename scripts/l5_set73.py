"""L5 (ADVANCED) reanalysis for set #73 tracks — standalone batch job.

Downloads MP3 from YM to a temp file, runs the full analyzer pipeline
(L1..L5 = all analyzers up to ADVANCED), upserts features at
analysis_level=5. Sequential, one track at a time (no process pool).

Run: env -u DJ_DATABASE_URL PYTHONUNBUFFERED=1 uv run python -u scripts/l5_set73.py
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
import time

with contextlib.suppress(Exception):
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
for noisy in ("httpx", "httpcore", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("l5")

from sqlalchemy import select

from app.audio.analyzers.base import AnalyzerRegistry
from app.audio.level_config import AnalysisLevel, get_analyzers_for_level
from app.audio.pipeline import AnalysisPipeline
from app.audio.temp_download import temp_download_track
from app.db.session import get_session_factory
from app.models.provider_metadata import YandexMetadata
from app.repositories.track_features import TrackFeaturesRepository
from app.server.lifespan import build_yandex_adapter

TRACK_IDS = [16760, 13066, 24325, 18843, 17687, 11873, 18628, 4051, 21971, 10011, 4558, 4520]
LEVEL = AnalysisLevel.ADVANCED  # 5


def _warmup_numba() -> None:
    """Prime numba JIT on the main thread (rules/audio.md SEGV guard)."""
    import librosa
    import numpy as np

    sr = 22050
    y = np.random.RandomState(42).randn(sr * 5).astype(np.float32) * 0.1
    librosa.onset.onset_strength(y=y, sr=sr)
    librosa.beat.beat_track(y=y, sr=sr)
    librosa.feature.chroma_cqt(y=y, sr=sr)
    librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    librosa.feature.spectral_centroid(y=y, sr=sr)


async def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(TRACK_IDS)
    track_ids = TRACK_IDS[:limit]
    total = len(track_ids)
    log.info("L5 batch start: %d track(s) at L%d", total, int(LEVEL))

    log.info("warming up numba JIT on main thread...")
    t0 = time.time()
    _warmup_numba()
    log.info("numba warmup done in %.1fs", time.time() - t0)

    registry = AnalyzerRegistry()
    registry.discover()
    pipeline = AnalysisPipeline(registry)  # default = thread pool, no process pool
    analyzers = get_analyzers_for_level(LEVEL)
    log.info("L5 analyzers (%d): %s", len(analyzers), ",".join(analyzers))

    adapter = build_yandex_adapter()
    client = adapter._client  # YandexClient with download_track

    sf = get_session_factory()
    async with sf() as session:
        ym_rows = (
            await session.execute(
                select(YandexMetadata.track_id, YandexMetadata.yandex_track_id).where(
                    YandexMetadata.track_id.in_(track_ids)
                )
            )
        ).all()
    ym_map = {tid: ym for tid, ym in ym_rows}

    counters = {"done": 0, "ok": 0, "fail": 0}
    for tid in track_ids:
        t_start = time.time()
        ym_id = ym_map.get(tid)
        if ym_id is None:
            counters["done"] += 1
            counters["fail"] += 1
            log.error(
                "    [%d/%d] track=%s FAIL no ym_id (ok=%d fail=%d)",
                counters["done"],
                total,
                tid,
                counters["ok"],
                counters["fail"],
            )
            log.error("STOP: missing ym_id — investigate before continuing")
            return
        try:
            async with temp_download_track(client, str(ym_id)) as path:
                result = await pipeline.analyze(str(path), analyzers=analyzers)
            sf2 = get_session_factory()
            async with sf2() as session:
                repo = TrackFeaturesRepository(session)
                await repo.upsert_analysis(
                    track_id=tid, analysis_level=int(LEVEL), **result.features
                )
                await session.commit()
            counters["done"] += 1
            counters["ok"] += 1
            n_err = len(getattr(result, "errors", []) or [])
            log.info(
                "    [%d/%d] track=%s ym=%s OK in %.1fs feats=%d analyzer_errs=%d (ok=%d fail=%d)",
                counters["done"],
                total,
                tid,
                ym_id,
                time.time() - t_start,
                len(result.features),
                n_err,
                counters["ok"],
                counters["fail"],
            )
        except Exception as exc:
            counters["done"] += 1
            counters["fail"] += 1
            log.error(
                "    [%d/%d] track=%s ym=%s FAIL in %.1fs: %r (ok=%d fail=%d)",
                counters["done"],
                total,
                tid,
                ym_id,
                time.time() - t_start,
                exc,
                counters["ok"],
                counters["fail"],
            )
            if counters["ok"] == 0:
                log.error("STOP: first track failed — not burning the rest blindly")
                return

    log.info("L5 batch done: ok=%d fail=%d of %d", counters["ok"], counters["fail"], total)


if __name__ == "__main__":
    asyncio.run(main())
