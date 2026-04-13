#!/usr/bin/env python3
"""Re-analyze all tracks with fixed BeatDetector.

After the beat detection fix (onset_detect → beat_track + downbeat detection),
all beat-dependent features in the DB are wrong. Migration c3f8a7b21d04 already
NULLed them and downgraded analysis_level to 2 (TRIAGE).

This script triggers re-analysis at SCORING level (L3) for ALL tracks,
which runs the fixed BeatDetector + dependent analyzers (beats_loudness,
bpm_histogram, phrase) and writes correct values to the DB.

Usage:
    uv run python scripts/reanalyze_beats.py

Requires: DJ_YM_TOKEN and DJ_DATABASE_URL in .env (for YM download + DB access).
"""

from __future__ import annotations

import asyncio
import sys
import time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


async def main() -> None:
    from app.audio.analyzers import AnalyzerRegistry
    from app.audio.level_config import AnalysisLevel
    from app.audio.pipeline import AnalysisPipeline
    from app.config import settings
    from app.models.audio import TrackAudioFeaturesComputed
    from app.models.track import Track
    from app.repositories.audio import AudioRepository
    from app.repositories.track import TrackRepository
    from app.services.tiered_pipeline import TieredPipeline
    from app.ym.client import YandexMusicClient

    print("=" * 60)
    print("BEAT RE-ANALYSIS — all tracks with fixed BeatDetector")
    print("=" * 60)
    print(f"DB: {settings.database_url[:50]}...")
    print(f"YM token: {'set' if settings.ym_token else 'MISSING'}")
    print()

    if not settings.ym_token:
        print("ERROR: DJ_YM_TOKEN not set. Need YM access to download audio.")
        sys.exit(1)

    engine = create_async_engine(settings.database_url, echo=False)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        # Count tracks
        total = (await session.execute(select(func.count(Track.id)))).scalar() or 0
        needs_beat = (
            await session.execute(
                select(func.count(TrackAudioFeaturesComputed.track_id)).where(
                    TrackAudioFeaturesComputed.analysis_level < AnalysisLevel.SCORING
                )
            )
        ).scalar() or 0
        no_features = (
            total
            - (
                await session.execute(select(func.count(TrackAudioFeaturesComputed.track_id)))
            ).scalar_one()
        )

        print(f"Total tracks:          {total}")
        print(f"Need beat re-analysis: {needs_beat}")
        print(f"No features at all:    {no_features}")
        print()

        if needs_beat == 0:
            print("Nothing to re-analyze. All tracks already at SCORING level.")
            return

        # Get track IDs needing re-analysis
        track_ids_result = await session.execute(
            select(TrackAudioFeaturesComputed.track_id).where(
                TrackAudioFeaturesComputed.analysis_level < AnalysisLevel.SCORING
            )
        )
        track_ids = [row[0] for row in track_ids_result.all()]

        print(f"Re-analyzing {len(track_ids)} tracks at SCORING level (L3)...")
        print("This runs: BeatDetector + BeatsLoudness + BpmHistogram + Phrase")
        print()

        # Setup pipeline
        registry = AnalyzerRegistry()
        registry.discover()
        pipeline = AnalysisPipeline(registry)

        async with YandexMusicClient(
            token=settings.ym_token,
            base_url=settings.ym_base_url,
        ) as ym_client:
            audio_repo = AudioRepository(session)
            track_repo = TrackRepository(session)
            tiered = TieredPipeline(audio_repo, track_repo, pipeline, ym_client)

            t0 = time.perf_counter()
            result = await tiered.ensure_level(track_ids, AnalysisLevel.SCORING)
            elapsed = time.perf_counter() - t0

            await session.commit()

        print()
        print("=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"  Analyzed: {result['analyzed']}")
        print(f"  Skipped:  {result['skipped']}")
        print(f"  Failed:   {result['failed']}")
        print(f"  Time:     {elapsed:.1f}s ({elapsed / max(result['analyzed'], 1):.1f}s/track)")
        print()

        # Verify a few tracks
        print("Sample results (first 5 re-analyzed tracks):")
        for tid in track_ids[:5]:
            feat = await audio_repo.get_features_by_track_id(tid)
            if feat:
                print(f"  Track {tid}:")
                print(f"    onset_rate={feat.onset_rate}, kick={feat.kick_prominence}")
                print(f"    pulse_clarity={feat.pulse_clarity}, hp_ratio={feat.hp_ratio}")
                print(f"    analysis_level={feat.analysis_level}")

        print()
        print("DONE. All beat features updated with fixed BeatDetector.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
