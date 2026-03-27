"""Benchmark audio analysis and set building with real MP3 files.

Usage: uv run python scripts/benchmark_audio.py
"""

from __future__ import annotations

import asyncio
import time

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings


async def make_session() -> AsyncSession:
    engine = create_async_engine(settings.database_url, echo=False)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    return session


async def main() -> None:
    session = await make_session()

    from app.repositories.feature import FeatureRepository
    from app.repositories.playlist import PlaylistRepository
    from app.repositories.set import SetRepository
    from app.repositories.track import TrackRepository
    from app.repositories.transition import TransitionRepository
    from app.services.set_service import SetService
    from app.services.track_service import TrackService

    track_repo = TrackRepository(session)
    feature_repo = FeatureRepository(session)
    playlist_repo = PlaylistRepository(session)
    set_repo = SetRepository(session)
    transition_repo = TransitionRepository(session)
    TrackService(track_repo, feature_repo)
    set_svc = SetService(set_repo, track_repo, playlist_repo, feature_repo, transition_repo)

    print("=" * 70)
    print("DJ Music Plugin — Audio & Set Building Benchmark")
    print("=" * 70)

    results: list[tuple[str, float, str]] = []

    def record(name: str, ms: float, detail: str = "") -> None:
        results.append((name, ms, detail))
        cat = "SLOW" if ms > 5000 else "MED" if ms > 500 else "FAST"
        print(f"  [{cat:4s}] {ms:10.1f}ms  {name}  — {detail}")

    # ── 1. Single track analysis (force re-analyze track 1) ──
    print("\n--- Audio Analysis (single track) ---")

    from app.audio.pipeline import AnalysisPipeline
    from app.audio.registry import AnalyzerRegistry

    registry = AnalyzerRegistry()
    registry.discover()
    pipeline = AnalysisPipeline(registry)

    # Find library item for track 1
    from sqlalchemy import select

    from app.models.library import DjLibraryItem

    lib_item = (
        await session.execute(select(DjLibraryItem).where(DjLibraryItem.track_id == 1))
    ).scalar_one_or_none()

    if lib_item:
        t0 = time.perf_counter()
        result = await pipeline.analyze(str(lib_item.file_path))
        t1 = time.perf_counter()
        record(
            "pipeline.analyze(track 1)",
            (t1 - t0) * 1000,
            f"features={len(result.features)}, errors={len(result.errors)}, "
            f"analyzers={[a for a in result.features] if hasattr(result, 'analyzers') else 'N/A'}",
        )

        # Individual analyzer breakdown
        print("\n  Analyzer breakdown (re-running individually):")
        # Use pipeline's internal loader to get AudioSignal
        audio = await pipeline._load_audio(str(lib_item.file_path))

        for analyzer_name in registry.list_available():
            analyzer = registry.get(analyzer_name)
            if analyzer is None:
                continue
            t0 = time.perf_counter()
            try:
                await analyzer.analyze(audio)
                t1 = time.perf_counter()
                record(f"  {analyzer.name}", (t1 - t0) * 1000, "OK")
            except Exception as e:
                t1 = time.perf_counter()
                record(f"  {analyzer.name}", (t1 - t0) * 1000, f"ERROR: {e}")
    else:
        print("  NO library item for track 1 — skipping audio analysis")

    # ── 2. Batch analysis (tracks 2-5) ──
    print("\n--- Audio Analysis (batch 4 tracks) ---")
    lib_items = (
        (
            await session.execute(
                select(DjLibraryItem).where(DjLibraryItem.track_id.in_([2, 3, 4, 5]))
            )
        )
        .scalars()
        .all()
    )

    if lib_items:
        t0 = time.perf_counter()
        for item in lib_items:
            await pipeline.analyze(str(item.file_path))
        t1 = time.perf_counter()
        total_batch = (t1 - t0) * 1000
        per_track = total_batch / len(lib_items)
        record(
            f"pipeline.analyze(batch {len(lib_items)} tracks)",
            total_batch,
            f"avg={per_track:.0f}ms/track",
        )

    # ── 3. Mood classification ──
    print("\n--- Mood Classification ---")
    from app.audio.mood import MoodClassifier

    classifier = MoodClassifier()
    track_ids = [1, 2, 3, 4, 5]

    t0 = time.perf_counter()
    for tid in track_ids:
        feat_row = await feature_repo.get_features(tid)
        if feat_row:
            # Convert DB row to feature dict for classifier
            feat_dict = {
                c.key: getattr(feat_row, c.key)
                for c in feat_row.__table__.columns
                if c.key not in ("track_id", "created_at", "updated_at")
                and getattr(feat_row, c.key) is not None
            }
            classifier.classify(feat_dict)
    t1 = time.perf_counter()
    record("classify_mood(5 tracks)", (t1 - t0) * 1000)

    # ── 4. Transition scoring with real features ──
    print("\n--- Transition Scoring ---")
    from app.services.transition import TransitionScorer

    scorer = TransitionScorer()

    # Score all pairs among 5 tracks
    features_map = await feature_repo.get_scoring_features_batch(track_ids)

    t0 = time.perf_counter()
    scored = 0
    for i, tid_a in enumerate(track_ids):
        for tid_b in track_ids[i + 1 :]:
            fa = features_map.get(tid_a)
            fb = features_map.get(tid_b)
            if fa and fb:
                scorer.score(fa, fb)
                scored += 1
    t1 = time.perf_counter()
    record(f"score_transitions({scored} pairs)", (t1 - t0) * 1000, "C(5,2)=10 pairs")

    # ── 5. Build set with features ──
    print("\n--- Set Building (with features) ---")

    t0 = time.perf_counter()
    try:
        result = await set_svc.build_set(
            playlist_id=1,
            name="Benchmark Set v2",
            algorithm="greedy",
            template="classic_60",
        )
        t1 = time.perf_counter()
        if isinstance(result, tuple):
            record(
                "build_set(greedy, features)",
                (t1 - t0) * 1000,
                f"tracks={result[0].id if result[0] else '?'}",
            )
        else:
            record("build_set(greedy, features)", (t1 - t0) * 1000, str(type(result)))
    except Exception as e:
        t1 = time.perf_counter()
        record("build_set(greedy, features)", (t1 - t0) * 1000, f"ERROR: {e}")

    # ── 6. Get set with transitions ──
    print("\n--- Set Retrieval ---")

    t0 = time.perf_counter()
    set_data = await set_svc.get_set(id=1, view="full")
    t1 = time.perf_counter()
    record("get_set(view=full)", (t1 - t0) * 1000, f"{len(set_data.get('tracks', []))} tracks")

    await session.close()

    # ── Summary ──
    print("\n" + "=" * 70)
    print("SUMMARY — sorted by duration (slowest first)")
    print("=" * 70)
    for name, ms, _detail in sorted(results, key=lambda x: x[1], reverse=True):
        if not name.startswith("  "):  # skip individual analyzers in summary
            cat = "SLOW" if ms > 5000 else "MED" if ms > 500 else "FAST"
            print(f"  [{cat:4s}] {ms:10.1f}ms  {name}")

    total_ms = sum(ms for name, ms, _ in results if not name.startswith("  "))
    print(f"\n  Total (top-level): {total_ms:.1f}ms")
    print("\n  Extrapolation for 3000 tracks:")
    # Find per-track analysis time
    batch_results = [ms for name, ms, _ in results if "batch" in name and "pipeline" in name]
    if batch_results:
        per_track = batch_results[0] / 4
        print(
            f"  Audio analysis: {per_track:.0f}ms/track × 3000 = {per_track * 3000 / 1000 / 60:.1f} minutes"
        )


if __name__ == "__main__":
    asyncio.run(main())
