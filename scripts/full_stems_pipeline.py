"""Structured set pipeline: warm-up → build → peak → cool-down → closing.

Phases: create tracks → audio files → L2 analyze → filter by structure → L5 → score → optimize → build → render
"""
import asyncio, contextlib, hashlib, os, re, sys, time
from pathlib import Path
from collections import Counter

from fastmcp import Client
from sqlalchemy import select

from app.audio.analyzers.base import AnalyzerRegistry
from app.audio.level_config import AnalysisLevel, get_analyzers_for_level
from app.audio.pipeline import AnalysisPipeline
from app.db.session import get_session_factory
from app.models.audio_file import DjBeatgrid, DjLibraryItem
from app.models.track import Track
from app.models.track_features import TrackAudioFeaturesComputed
from app.repositories.track_features import TrackFeaturesRepository
from app.repositories.unit_of_work import UnitOfWork
from app.server.app import build_mcp_server

STEMS_DIR = Path("/Users/laptop/Desktop/Stems")
STEM_TYPES = "acappella|bass|drums|harmonic|instrumental"
PATTERN = re.compile(
    rf"^(?P<index>\d+)\s+\[(?P<bpm>\d+)bpm\]\s+\[(?P<genre>\w+)\]\s+(?P<title>.+)-(?P<stem>{STEM_TYPES})\.m4a$"
)


def file_hash(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        sha.update(f.read(1_048_576))
    return sha.hexdigest()[:64]


def parse_stems() -> dict[int, dict]:
    tracks: dict[int, dict] = {}
    for f in sorted(STEMS_DIR.iterdir()):
        if f.is_dir() or f.name.startswith("."):
            continue
        m = PATTERN.match(f.name)
        if not m:
            continue
        idx = int(m.group("index"))
        if idx not in tracks:
            tracks[idx] = {
                "title": m.group("title"),
                "bpm": int(m.group("bpm")),
                "genre": m.group("genre"),
                "stems": {},
            }
        tracks[idx]["stems"][m.group("stem")] = str(f)
    return tracks


async def analyze_batch(track_ids: list[int], level: int = 3, max_count: int = 40):
    """L2/L3 analysis of unanalyzed tracks."""
    registry = AnalyzerRegistry()
    with contextlib.suppress(Exception):
        registry.discover()
    pipeline = AnalysisPipeline(registry)
    sf = get_session_factory()
    analyzed, count = [], 0

    for tid in track_ids:
        if count >= max_count:
            break
        async with sf() as s:
            lvl = await s.execute(
                select(TrackAudioFeaturesComputed.analysis_level)
                .where(TrackAudioFeaturesComputed.track_id == tid)
            )
            if (lvl.scalar() or 0) >= 2:
                continue
            fp = await s.execute(
                select(DjLibraryItem.file_path).where(DjLibraryItem.track_id == tid).limit(1)
            )
            fp = fp.scalar()
            if not fp:
                continue
            t0 = time.time()
            try:
                res = await pipeline.analyze(fp)
                repo = TrackFeaturesRepository(s)
                await repo.upsert_analysis(track_id=tid, analysis_level=level, **res.features)
                await s.commit()
                analyzed.append(tid)
                count += 1
                e = res.features.get("energy_mean", 0)
                b = res.features.get("bpm", "?")
                print(f"  [{count}/{max_count}] #{tid} OK {time.time()-t0:.0f}s BPM={b} E={e:.3f}")
            except Exception as exc:
                print(f"  [#{tid}] FAIL: {exc}")
    return analyzed


async def l5_batch(track_ids: list[int]):
    """L5 reanalysis."""
    registry = AnalyzerRegistry()
    with contextlib.suppress(Exception):
        registry.discover()
    pipeline = AnalysisPipeline(registry)
    analyzers = get_analyzers_for_level(AnalysisLevel.ADVANCED)
    sf = get_session_factory()
    ok = fail = 0
    for i, tid in enumerate(track_ids):
        t0 = time.time()
        try:
            async with sf() as s:
                fp = await s.execute(
                    select(DjLibraryItem.file_path).where(DjLibraryItem.track_id == tid).limit(1)
                )
                fp = fp.scalar()
                if not fp:
                    print(f"  [{i+1}/{len(track_ids)}] #{tid} FAIL: no audio")
                    fail += 1; continue
                res = await pipeline.analyze(fp, analyzers=analyzers)
                repo = TrackFeaturesRepository(s)
                await repo.upsert_analysis(track_id=tid, analysis_level=5, **res.features)
                await s.commit()
            ok += 1
            key = res.features.get("key_code", "?")
            e = res.features.get("energy_mean", 0)
            print(f"  [{i+1}/{len(track_ids)}] #{tid} OK {time.time()-t0:.0f}s key={key} E={e:.3f} (ok={ok} fail={fail})")
        except Exception as exc:
            fail += 1
            print(f"  [{i+1}/{len(track_ids)}] #{tid} FAIL: {exc}")
    print(f"L5 done: ok={ok} fail={fail}")


async def main():
    # ── 1. Parse ──
    print("=" * 70)
    print("PHASE 1: Parse stems")
    all_t = parse_stems()
    print(f"Total: {len(all_t)} tracks")
    genres = Counter(t["genre"] for t in all_t.values())
    print(f"Genres: {dict(genres.most_common(10))}")

    # ── 2. Select candidates across the energy arc ──
    target = {"driving", "peak_time", "acid", "industrial", "hard_techno"}

    # Structure zones (index → BPM range):
    zones = {
        "warmup":  (126, 129, 5),
        "build":   (128, 132, 6),
        "peak":    (132, 138, 7),
        "cooldown":(130, 134, 4),
        "closing": (126, 130, 3),
    }

    # Select by zone: pick tracks closest to zone BPM, preferring genre diversity
    selected_indices = set()
    for zone_name, (bpm_lo, bpm_hi, count) in zones.items():
        candidates = [
            (idx, t) for idx, t in all_t.items()
            if t["genre"] in target and bpm_lo <= t["bpm"] <= bpm_hi
        ]
        # Sort by how close to zone center
        center = (bpm_lo + bpm_hi) / 2
        candidates.sort(key=lambda x: abs(x[1]["bpm"] - center))
        
        # Take diverse genres
        seen_genres = set()
        zone_selected = []
        for idx, t in candidates:
            if idx in selected_indices:
                continue
            if t["genre"] not in seen_genres or len(zone_selected) < count // 2:
                zone_selected.append(idx)
                seen_genres.add(t["genre"])
                selected_indices.add(idx)
            if len(zone_selected) >= count:
                break
        
        print(f"\n{zone_name.upper()} ({bpm_lo}-{bpm_hi} BPM): {len(zone_selected)} selected")
        for idx in zone_selected[:count]:
            t = all_t[idx]
            print(f"  {idx:04d} [{t['bpm']}bpm] [{t['genre']:<14}] {t['title'][:50]}")

    total_selected = len(selected_indices)
    print(f"\nTotal selected: {total_selected} tracks across 5 zones")

    # ── 3. Create tracks ──
    print(f"\n{'=' * 70}")
    print("PHASE 2: Create tracks in library")

    mcp = build_mcp_server()
    async with Client(mcp) as client:
        r = await client.call_tool("entity_list", {
            "entity": "track", "limit": 500, "with_total": True,
        })
        existing = {t.get("title", "").lower(): t["id"] for t in r.structured_content.get("items", [])}

    id_map = {}
    new_t = {}
    for idx in sorted(selected_indices):
        t = all_t[idx]
        if t["title"].lower() in existing:
            id_map[idx] = existing[t["title"].lower()]
        else:
            new_t[idx] = t

    if new_t:
        sf = get_session_factory()
        async with sf() as s:
            async with UnitOfWork(s) as uow:
                for idx in sorted(new_t):
                    t = new_t[idx]
                    row = await uow.tracks.create(
                        title=t["title"], sort_title=t["title"].lower(), duration_ms=None,
                    )
                    id_map[idx] = row.id
        print(f"Created {len(new_t)} new tracks")
    else:
        print("All already exist")

    sel_ids = sorted(id_map[idx] for idx in selected_indices if idx in id_map)
    print(f"Track IDs ({len(sel_ids)}): {sel_ids}")

    # ── 4. Audio files ──
    print(f"\n{'=' * 70}")
    print("PHASE 3: Audio files")

    if new_t:
        sf = get_session_factory()
        async with sf() as s:
            new_ids = [id_map[idx] for idx in new_t]
            r = await s.execute(
                select(DjLibraryItem.track_id).where(DjLibraryItem.track_id.in_(new_ids))
            )
            have = {row.track_id for row in r}

            async with UnitOfWork(s) as uow:
                created = 0
                for idx in new_t:
                    tid = id_map[idx]
                    if tid in have:
                        continue
                    t = new_t[idx]
                    for stype in ["instrumental", "drums"]:
                        path = t["stems"].get(stype)
                        if not path:
                            continue
                        item = DjLibraryItem(
                            track_id=tid, file_path=path,
                            file_hash=file_hash(path), file_size=os.path.getsize(path),
                            mime_type="audio/mp4", source_app="suno_stems",
                        )
                        uow.session.add(item)
                        await uow.session.flush()
                        uow.session.add(DjBeatgrid(
                            library_item_id=item.id, bpm=float(t["bpm"]),
                            confidence=0.95, canonical=(stype == "instrumental"),
                            variable_tempo=False,
                        ))
                        created += 1
            print(f"Created {created} audio records")

    # ── 5. L2 Analysis ──
    print(f"\n{'=' * 70}")
    print("PHASE 4: L2 Analysis (up to 30 tracks)")
    analyzed = await analyze_batch(sel_ids, level=3, max_count=30)
    print(f"Analyzed: {len(analyzed)}")

    # ── 6. Query features, build structured pool ──
    print(f"\n{'=' * 70}")
    print("PHASE 5: Feature-based pool selection")

    sf = get_session_factory()
    async with sf() as s:
        r = await s.execute(
            select(Track.id, Track.title,
                   TrackAudioFeaturesComputed.bpm,
                   TrackAudioFeaturesComputed.energy_mean,
                   TrackAudioFeaturesComputed.integrated_lufs,
                   TrackAudioFeaturesComputed.key_code,
                   TrackAudioFeaturesComputed.analysis_level,
                   TrackAudioFeaturesComputed.spectral_centroid_hz)
            .join(TrackAudioFeaturesComputed, Track.id == TrackAudioFeaturesComputed.track_id)
            .where(Track.id.in_(sel_ids))
            .where(TrackAudioFeaturesComputed.energy_mean >= 0.25)
            .where(TrackAudioFeaturesComputed.integrated_lufs >= -14)
            .where(TrackAudioFeaturesComputed.bpm.between(124, 142))
        )
        rows = r.all()

    # Sort by BPM, then pick top by energy within BPM bands
    rows_by_bpm = sorted(rows, key=lambda r: (r.bpm or 0, -(r.energy_mean or 0)))

    # Select ~20 tracks with BPM diversity and high energy
    final_pool = []
    seen_bpms = set()
    for row in rows_by_bpm:
        bpm_bin = int(row.bpm or 0)
        if bpm_bin not in seen_bpms or len(final_pool) < 15:
            seen_bpms.add(bpm_bin)
            final_pool.append(row.id)
        if len(final_pool) >= 22:
            break

    print(f"Final pool: {len(final_pool)} tracks")
    for row in rows_by_bpm:
        if row.id in final_pool:
            print(f"  #{row.id:<5} {row.title[:45]:<46} {row.bpm:>6.1f} E={row.energy_mean:.3f} LUFS={row.integrated_lufs:.1f} key={row.key_code}")

    if len(final_pool) < 10:
        print("Pool too small, using all available")
        final_pool = [r.id for r in rows][:22]

    # ── 7. L5 ──
    print(f"\n{'=' * 70}")
    print("PHASE 6: L5 Analysis")
    need_l5 = []
    async with sf() as s:
        r = await s.execute(
            select(TrackAudioFeaturesComputed.track_id, TrackAudioFeaturesComputed.analysis_level)
            .where(TrackAudioFeaturesComputed.track_id.in_(final_pool))
        )
        for row in r:
            if (row.analysis_level or 0) < 5:
                need_l5.append(row.track_id)
    print(f"Need L5: {len(need_l5)}/{len(final_pool)}")
    if need_l5:
        await l5_batch(need_l5)

    # ── 8. Score + Optimize + Build + Render ──
    print(f"\n{'=' * 70}")
    print("PHASE 7: Score → Optimize → Build → Render")

    async with Client(mcp) as client:
        # Score
        r = await client.call_tool("transition_score_pool", {
            "track_ids": final_pool, "top_k": 3, "components": False,
        })
        sc = r.structured_content
        print(f"Scored: {sc.get('total_scored_pairs')} pairs, {sc.get('hard_rejects')} rejects")

        # GA
        r = await client.call_tool("sequence_optimize", {
            "track_ids": final_pool, "algorithm": "ga", "template": "roller_90",
        })
        ga = r.structured_content
        ga_order = ga.get("track_order", [])
        print(f"GA: raw={ga.get('quality_score',0):.4f}, {len(ga_order)} tracks")

        # Greedy
        r = await client.call_tool("sequence_optimize", {
            "track_ids": final_pool, "algorithm": "greedy", "template": "roller_90",
        })
        gr = r.structured_content
        gr_order = gr.get("track_order", [])
        print(f"Greedy: raw={gr.get('quality_score',0):.4f}, {len(gr_order)} tracks")

        # Create set
        r = await client.call_tool("entity_create", {
            "entity": "set",
            "data": {
                "name": "Stems Hard Set — Multigenre 5-Zone",
                "template_name": "roller_90",
                "target_duration_ms": len(final_pool) * 390000,
            },
        })
        set_id = r.structured_content.get("data", {}).get("id", "?")
        print(f"Set: #{set_id}")

        # Create versions
        for algo, label, order in [
            ("ga", "v1-ga", ga_order),
            ("greedy", "v2-greedy", gr_order),
        ]:
            r = await client.call_tool("entity_create", {
                "entity": "set_version",
                "data": {"set_id": set_id, "label": label, "track_order": order},
            })
            vd = r.structured_content.get("data", {})
            print(f"  {label}: id={vd.get('id','?')} section_score={vd.get('quality_score','?')}")

        # Pick winner for render
        r = await client.call_tool("entity_get", {
            "entity": "set", "id": set_id, "include_relations": ["versions"],
        })
        versions = r.structured_content.get("data", {}).get("versions", [])
        if versions:
            best = max(versions, key=lambda v: v.get("quality_score", 0))
            render_id = best["id"]
            print(f"\nRendering version {render_id} ({best['label']}, score={best['quality_score']:.4f})")

            # Ensure audio
            r = await client.call_tool("entity_list", {
                "entity": "audio_file",
                "filters": {"track_id__in": final_pool},
                "limit": 30, "fields": ["track_id"],
            })
            have = {it["track_id"] for it in r.structured_content.get("items", [])}
            missing = [tid for tid in final_pool if tid not in have]
            if missing:
                print(f"Downloading {len(missing)} audio files...")
                await client.call_tool("entity_create", {
                    "entity": "audio_file", "data": {"track_ids": missing},
                })

            print(f"Rendering ({len(final_pool)} tracks, EQ bass-swap)...")
            r = await client.call_tool("render_mixdown", {
                "version_id": render_id,
                "out_name": "Stems_Hard_Set_5Zone.mp3",
                "stem": False,
            })
            rd = r.structured_content
            if hasattr(rd, "model_dump"):
                rd = rd.model_dump()
            print(f"\n{'=' * 70}")
            print(f"RENDER COMPLETE")
            print(f"  Set: #{set_id}")
            print(f"  Version: {render_id} ({best['label']})")
            print(f"  File: {rd.get('out_path')}")
            print(f"  Duration: {rd.get('duration_s',0):.0f}s ({rd.get('duration_s',0)/60:.0f} min)")
            print(f"  True peak: {rd.get('true_peak_db')} dB")
            print(f"  Level jumps: {rd.get('level_jumps')}")

    print(f"\n{'=' * 70}")
    print("PIPELINE COMPLETE")


if __name__ == "__main__":
    asyncio.run(main())
