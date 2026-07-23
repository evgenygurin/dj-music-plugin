"""Step 3-4: Analyze new stem tracks, filter pool, then score + optimize + build set.

Run: PYTHONUNBUFFERED=1 uv run python -u scripts/step3_analyze_and_build.py
"""
import asyncio
import contextlib
import sys
import time
from pathlib import Path
from typing import Any

from fastmcp import Client
from app.audio.analyzers.base import AnalyzerRegistry
from app.audio.pipeline import AnalysisPipeline
from app.db.session import get_session_factory
from app.repositories.unit_of_work import UnitOfWork
from app.server.app import build_mcp_server
from sqlalchemy import select

from app.models.audio_file import DjLibraryItem
from app.models.track import Track
from app.models.track_features import TrackAudioFeaturesComputed


class FakeCtx:
    async def info(self, msg: str) -> None:
        print(f"  [info] {msg}")
    async def report_progress(self, progress: int, total: int, message: str | None = None) -> None:
        pass
    async def log(self, level: str, msg: str) -> None:
        pass


async def analyze_tracks_direct(track_ids: list[int], level: int = 3):
    """Analyze tracks directly (no MCP) using pipeline."""
    registry = AnalyzerRegistry()
    with contextlib.suppress(Exception):
        registry.discover()
    pipeline = AnalysisPipeline(registry)
    print(f"  Analyzers: {registry.list_available()}")

    sf = get_session_factory()
    analyzed = []
    skipped = []
    errors = []

    for i, tid in enumerate(track_ids):
        async with sf() as session:
            async with UnitOfWork(session) as uow:
                track = await uow.tracks.get(tid)
                if track is None:
                    errors.append({"track_id": tid, "error": "not found"})
                    continue

                existing = await uow.track_features.get_by_track_id(tid)
                if existing is not None:
                    current = int(getattr(existing, "analysis_level", 0) or 0)
                    if current >= level:
                        skipped.append({"track_id": tid, "level": current})
                        continue

                lib = await uow.audio_files.get_by_track_id(tid)
                if lib is None:
                    errors.append({"track_id": tid, "error": "no audio file"})
                    continue

                t0 = time.time()
                try:
                    result = await pipeline.analyze(lib.file_path)
                except Exception as exc:
                    errors.append({"track_id": tid, "error": str(exc)})
                    print(f"  [{i+1}/{len(track_ids)}] track={tid} ERROR: {exc}")
                    continue

                await uow.track_features.upsert_analysis(
                    track_id=tid,
                    analysis_level=level,
                    **result.features,
                )

                elapsed = time.time() - t0
                bpm = result.features.get("bpm", "?")
                energy = result.features.get("energy_mean", "?")
                analyzed.append({"track_id": tid, "level": level, "features": len(result.features)})
                print(f"  [{i+1}/{len(track_ids)}] track={tid} OK {elapsed:.1f}s  BPM={bpm}  E={energy}  feats={len(result.features)}")

    print(f"\n  Analyzed: {len(analyzed)}, Skipped: {len(skipped)}, Errors: {len(errors)}")
    if errors:
        for e in errors:
            print(f"    Error: track={e['track_id']} — {e['error']}")
    return analyzed, skipped, errors


async def main():
    # Existing good tracks (from previous analysis)
    EXISTING_GOOD = [
        # track_id, title, bpm, energy
        (161, "This Is Hot", 128, 0.49),
        (172, "Temptation", 128, 0.45),
        (184, "Deep in Your Love", 130, 0.47),
        (214, "Techno Addicted", 126, 0.47),
        (291, "Berserker", 128, 0.56),
        (451, "Lost Eyes", 128, 0.42),
        (554, "Inappropriate Tentacle Proclivity", 128, 0.39),
    ]

    # Start with 5 tracks, then add more on rerun
    NEW_TO_ANALYZE = [
        29582, 29587, 29588, 29594, 29598, 29599, 29602, 29606, 29607, 29608,
    ]

    # Also include previously analyzed tracks
    PREVIOUSLY_ANALYZED = [29581, 29584, 29586, 29600, 29603]

    print("=== Phase A: Analyze new stem tracks (L2) ===")
    print(f"Analyzing {len(NEW_TO_ANALYZE)} new tracks...")
    
    analyzed, skipped, errors = await analyze_tracks_direct(NEW_TO_ANALYZE, level=3)

    # Combine pool
    good_new_ids = [a["track_id"] for a in analyzed] + PREVIOUSLY_ANALYZED
    pool_ids = [t[0] for t in EXISTING_GOOD] + good_new_ids

    print(f"\n=== Phase B: Pool = {len(pool_ids)} tracks ===")

    # Query all features
    sf = get_session_factory()
    async with sf() as s:
        r = await s.execute(
            select(Track.id, Track.title, TrackAudioFeaturesComputed.bpm,
                   TrackAudioFeaturesComputed.energy_mean,
                   TrackAudioFeaturesComputed.integrated_lufs,
                   TrackAudioFeaturesComputed.key_code,
                   TrackAudioFeaturesComputed.analysis_level,
                   TrackAudioFeaturesComputed.spectral_centroid_hz)
            .outerjoin(TrackAudioFeaturesComputed)
            .where(Track.id.in_(pool_ids))
            .order_by(TrackAudioFeaturesComputed.energy_mean.desc().nullslast())
        )
        rows = r.all()

    print(f"\n{'ID':>5} {'Title':<40} {'BPM':>6} {'Energy':>7} {'LUFS':>6} {'Key':>4} {'Lvl':>3}")
    print('-' * 80)
    final_ids = []
    for row in rows:
        bpm = row.bpm or 0
        energy = row.energy_mean or 0
        lufs = row.integrated_lufs or -99
        if bpm >= 124 and energy >= 0.25 and lufs >= -15:
            final_ids.append(row.id)
        print(f'{row.id:>5} {row.title[:38]:<40} {bpm:>6.1f} {energy:>7.3f} {lufs:>6.1f} {row.key_code or "?":>4} {row.analysis_level or 0:>3}')
        if row.id not in final_ids:
            print(f'      ^ filtered out')

    print(f"\nFinal pool: {len(final_ids)} tracks")
    print(f"IDs: {final_ids}")

    # Build set via MCP
    if len(final_ids) >= 5:
        print(f"\n=== Phase C: Score transitions ===")
        mcp = build_mcp_server()
        async with Client(mcp) as client:
            r = await client.call_tool("transition_score_pool", {
                "track_ids": final_ids,
                "top_k": 3,
                "components": False,
            })
            data = r.structured_content
            print(f"  Pairs scored: {data.get('total_scored_pairs', '?')}")

            # Show hard rejects
            hard_reject_count = data.get("hard_rejects", 0)
            print(f"  Hard rejects: {hard_reject_count}")
            
            print(f"\n=== Phase D: Optimize order (GA) ===")
            r = await client.call_tool("sequence_optimize", {
                "track_ids": final_ids,
                "algorithm": "ga",
            })
            opt = r.structured_content
            order = opt.get("track_order", [])
            score = opt.get("quality_score", 0)
            print(f"  GA quality score: {score:.4f}")
            print(f"  Track order ({len(order)}): {order}")

            # Also greedy for comparison
            r = await client.call_tool("sequence_optimize", {
                "track_ids": final_ids,
                "algorithm": "greedy",
            })
            greedy = r.structured_content
            print(f"  Greedy quality score: {greedy.get('quality_score', 0):.4f}")

            print(f"\n=== Phase E: Create set ===")
            r = await client.call_tool("entity_create", {
                "entity": "set",
                "data": {
                    "name": "Stems Acid Set — 4-Deck Techno",
                    "template_name": "roller_90",
                    "target_duration_ms": len(final_ids) * 390000,
                },
            })
            sd = r.structured_content
            set_id = sd.get("data", {}).get("id", "?")
            print(f"  Set created: #{set_id}")

            # Create versions
            for algo, label, track_order in [
                ("ga", "v1-ga", order),
                ("greedy", "v2-greedy", greedy.get("track_order", order)),
            ]:
                r = await client.call_tool("entity_create", {
                    "entity": "set_version",
                    "data": {
                        "set_id": set_id,
                        "label": label,
                        "track_order": track_order,
                    },
                })
                vd = r.structured_content
                vs = vd.get("data", {}).get("quality_score", 0)
                print(f"  Version '{label}': score={vs:.4f}")

            print(f"\n=== DONE ===")
            print(f"Set ID: {set_id}")
            print(f"Check with: entity_get(entity='set', id={set_id}, fields='summary')")
    else:
        print(f"Pool too small ({len(final_ids)} < 8), need more analyzed tracks")


if __name__ == "__main__":
    asyncio.run(main())
