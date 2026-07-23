"""L5 analysis for set #1116 tracks — direct pipeline, no MCP."""
import asyncio
import contextlib
import sys
import time

from app.audio.analyzers.base import AnalyzerRegistry
from app.audio.level_config import AnalysisLevel, get_analyzers_for_level
from app.audio.pipeline import AnalysisPipeline
from app.db.session import get_session_factory
from app.models.audio_file import DjLibraryItem
from app.models.track import Track
from app.repositories.track_features import TrackFeaturesRepository
from sqlalchemy import select

L5_IDS = [554, 29581, 29582, 29584, 29586, 29587, 29588, 29594,
          29598, 29599, 29600, 29602, 29603, 29606, 29607, 29608]
LEVEL = int(AnalysisLevel.ADVANCED)


async def main():
    print(f"L5 batch: {len(L5_IDS)} tracks at level {LEVEL}")

    registry = AnalyzerRegistry()
    with contextlib.suppress(Exception):
        registry.discover()
    pipeline = AnalysisPipeline(registry)
    analyzers = get_analyzers_for_level(LEVEL)
    print(f"Analyzers: {len(analyzers)} — {','.join(analyzers[:5])}...")

    sf = get_session_factory()

    done = ok = fail = 0
    for i, tid in enumerate(L5_IDS):
        t0 = time.time()
        try:
            async with sf() as session:
                lib_row = await session.execute(
                    select(DjLibraryItem.file_path)
                    .where(DjLibraryItem.track_id == tid)
                    .limit(1)
                )
                fp = lib_row.scalar()
                if not fp:
                    print(f"  [{i+1}/{len(L5_IDS)}] track={tid} FAIL: no audio file")
                    fail += 1
                    done += 1
                    continue

                result = await pipeline.analyze(fp, analyzers=analyzers)

                repo = TrackFeaturesRepository(session)
                await repo.upsert_analysis(
                    track_id=tid, analysis_level=LEVEL, **result.features
                )
                await session.commit()

            elapsed = time.time() - t0
            bpm = result.features.get("bpm", "?")
            key = result.features.get("key_code", "?")
            energy = result.features.get("energy_mean", "?")
            n_err = len(getattr(result, "errors", []) or [])
            ok += 1
            print(f"  [{i+1}/{len(L5_IDS)}] track={tid} OK {elapsed:.1f}s "
                  f"BPM={bpm} key={key} E={energy:.3f} feats={len(result.features)} "
                  f"errs={n_err} (ok={ok} fail={fail})")

        except Exception as exc:
            done += 1
            fail += 1
            print(f"  [{i+1}/{len(L5_IDS)}] track={tid} FAIL {time.time()-t0:.1f}s: {exc}")
            if ok == 0:
                print("STOP: first track failed")
                return

        done += 1

    print(f"\nL5 done: ok={ok} fail={fail} of {len(L5_IDS)}")


if __name__ == "__main__":
    asyncio.run(main())
