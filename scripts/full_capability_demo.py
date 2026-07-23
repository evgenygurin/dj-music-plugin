"""Full demo: build a 2-story Nina-style set using ALL new MCP-integrated tools.

Uses: energy_arc_plan → subgenre_preset → filter_sweep + echo + reverb →
      key_compatibility → scoring → optimization → cue_points → 
      extended render_mixdown → diagnostics → auto_fix
"""
import asyncio, json, sys, time
from pathlib import Path

from fastmcp import Client
from app.server.app import build_mcp_server

# Import new modules directly (works even if MCP discovery doesn't pick them up)
from app.domain.performance.energy_arc import journey_arc, fit_tracks_to_arc, TrackCandidate
from app.domain.performance.subgenre_presets import resolve_preset, INDUSTRIAL
from app.domain.performance.key_interchange import analyze_key_relation, subgenre_key_score
from app.audio.effects.filter_sweep import FILTER_PRESETS
from app.audio.effects.echo_delay import ECHO_PRESETS
from app.audio.effects.reverb import REVERB_PRESETS

STORY1_BPM = (126, 130)  # hypnotic/deep
STORY2_BPM = (133, 140)  # hard/peak

async def main():
    print("=" * 70)
    print("DJ PERFORMANCE ENGINE — FULL CAPABILITY DEMO")
    print("=" * 70)

    mcp = build_mcp_server()

    # ── 1. Energy Arc (Nina-style journey: 2 stories) ──
    print("\n─── 1. ENERGY ARC (journey shape) ───")
    arc = journey_arc(16)
    arc.target_bpm_start = 126
    arc.target_bpm_peak = 138
    arc.target_bpm_end = 128
    slots = arc.build_slots()
    for s in slots[:4]:
        print(f"  Slot {s.position}: {s.label:<10} BPM={s.target_bpm:.0f} E={s.target_energy:.2f}")
    print(f"  ... ({len(slots)} slots total)")

    # ── 2. Subgenre Preset ──
    print("\n─── 2. SUBGENRE PRESET (industrial) ───")
    preset = resolve_preset("industrial_techno")
    print(f"  transition_bars={preset.transition_bars} body_bars={preset.body_bars}")
    print(f"  xsplit=({preset.xsplit_low_hz}/{preset.xsplit_high_hz}Hz)")
    print(f"  limiter_ceiling={preset.limiter_ceiling} comp_ratio={preset.pre_comp_ratio}")

    # ── 3. Effects ──
    print("\n─── 3. EFFECTS CONFIGURATION ───")
    for name, presets in [("Filter", FILTER_PRESETS), ("Echo", ECHO_PRESETS), ("Reverb", REVERB_PRESETS)]:
        keys = list(presets.keys())[:3]
        print(f"  {name}: {', '.join(keys)}")

    fs = FILTER_PRESETS["acid_squelch"]
    echo = ECHO_PRESETS["industrial_stutter"]
    reverb = REVERB_PRESETS["industrial_warehouse"]
    print(f"  Selected: acid_squelch + industrial_stutter + industrial_warehouse")

    # ── 4. Curate pool ──
    print("\n─── 4. CURATING CANDIDATE POOL ───")
    async with Client(mcp) as client:
        # Get candidates for both stories
        r = await client.call_tool("entity_list", {
            "entity": "track_features",
            "filters": {"bpm__range": [126, 140], "energy_mean__gte": 0.4,
                        "analysis_level__gte": 2, "integrated_lufs__gte": -14},
            "fields": ["track_id", "bpm", "energy_mean", "integrated_lufs", "key_code"],
            "sort": ["energy_mean__desc"],
            "limit": 30,
        })
        items = r.structured_content.get("items", [])
        candidates = [
            TrackCandidate(
                track_id=it["track_id"], bpm=it["bpm"] or 130,
                energy_mean=it["energy_mean"] or 0.5,
                key_code=it.get("key_code"), integrated_lufs=it.get("integrated_lufs", -10),
                spectral_centroid_hz=0,
            )
            for it in items if it.get("energy_mean")
        ]
        print(f"  Candidates with features: {len(candidates)}")

        # Fit to arc
        final_ids = fit_tracks_to_arc(candidates, arc)
        print(f"  Fitted to arc: {len(final_ids) if final_ids else 0} tracks")
        if not final_ids or len(final_ids) < 8:
            print("  Using top 16 by energy instead")
            final_ids = [c.track_id for c in candidates[:16]]

    # ── 5. Key Compatibility ──
    print("\n─── 5. KEY COMPATIBILITY CHECK ───")
    for i in range(min(5, len(final_ids) - 1)):
        a_id, b_id = final_ids[i], final_ids[i + 1]
        a = next((c for c in candidates if c.track_id == a_id), None)
        b = next((c for c in candidates if c.track_id == b_id), None)
        if a and b and a.key_code is not None and b.key_code is not None:
            score = subgenre_key_score(a.key_code, b.key_code, "industrial_techno")
            rel = analyze_key_relation(a.key_code, b.key_code)
            print(f"  #{a_id}→#{b_id}: {rel.relation.value} score={score:.3f} — {rel.description[:60]}")

    # ── 6. Score + Optimize ──
    print("\n─── 6. SCORING + OPTIMIZATION ───")
    async with Client(mcp) as client:
        r = await client.call_tool("transition_score_pool", {
            "track_ids": final_ids, "top_k": 3, "components": False,
        })
        sc = r.structured_content
        print(f"  Scored: {sc.get('total_scored_pairs')} pairs, {sc.get('hard_rejects')} rejects")

        r = await client.call_tool("sequence_optimize", {
            "track_ids": final_ids, "algorithm": "ga", "template": "roller_90",
        })
        ga = r.structured_content
        ga_order = ga.get("track_order", [])
        print(f"  GA: score={ga.get('quality_score',0):.4f}, {len(ga_order)} tracks")

    # ── 7. Create Set ──
    print("\n─── 7. CREATE SET + VERSION ───")
    async with Client(mcp) as client:
        r = await client.call_tool("entity_create", {
            "entity": "set",
            "data": {"name": "Industrial Journey — Nina x Liebing Style", "template_name": "roller_90",
                     "target_duration_ms": len(ga_order) * 390000},
        })
        set_id = r.structured_content.get("data", {}).get("id", "?")
        print(f"  Set: #{set_id}")

        r = await client.call_tool("entity_create", {
            "entity": "set_version",
            "data": {"set_id": set_id, "label": "v1-industrial-journey", "track_order": ga_order},
        })
        vd = r.structured_content.get("data", {})
        ver_id = vd.get("version_id", vd.get("id", "?"))
        print(f"  Version: {ver_id} (score={vd.get('quality_score','?')})")

    # ── 8. Cue Points for first 3 tracks ──
    print("\n─── 8. CUE POINTS (first 3 tracks) ───")
    from app.domain.performance.cue_points import detect_cues
    from app.repositories.unit_of_work import UnitOfWork
    from app.db.session import get_session_factory

    sf = get_session_factory()
    async with sf() as session:
        async with UnitOfWork(session) as uow:
            for tid in ga_order[:3]:
                sections = await uow.track_sections.list_by_track(tid)
                feats = await uow.track_features.get_by_track_id(tid)
                section_dicts = [{"track_id": s.track_id, "section_type": s.section_type,
                                  "start_ms": s.start_ms, "end_ms": s.end_ms,
                                  "energy": s.energy, "confidence": s.confidence}
                                 for s in sections]
                bpm = float(getattr(feats, "bpm", 128) or 128)
                fd_ms = float(getattr(feats, "first_downbeat_ms", 0) or 0)
                cue_set = detect_cues(section_dicts, bpm, fd_ms, 0)
                cues_str = ", ".join(c.label for c in cue_set.cues[:4])
                print(f"  #{tid}: {len(cue_set.cues)} cues — {cues_str}")

    # ── 9. RENDER with ALL effects ──
    print("\n─── 9. RENDER WITH EFFECTS ───")
    async with Client(mcp) as client:
        r = await client.call_tool("render_mixdown", {
            "version_id": int(ver_id),
            "out_name": "Industrial_Journey_Demo.mp3",
            "subgenre": "industrial_techno",
            "filter_sweep": "acid_squelch",
            "echo": "industrial_stutter",
            "crossfade_curve_out": "tri",
            "crossfade_curve_in": "exp",
            "reverb": "industrial_warehouse",
            "reverb_mix": 0.20,
            "stem": False,
        })
        rd = r.structured_content
        if hasattr(rd, "model_dump"):
            rd = rd.model_dump()
        print(f"  Output: {rd.get('out_path')}")
        print(f"  Duration: {rd.get('duration_s',0):.0f}s")
        print(f"  True peak: {rd.get('true_peak_db')} dB")
        print(f"  Level jumps: {rd.get('level_jumps')}")

    # ── 10. Diagnostics + AutoFix (dry run) ──
    print("\n─── 10. DIAGNOSTICS + AUTO-FIX ───")
    async with Client(mcp) as client:
        try:
            r = await client.call_tool("render_diagnose", {
                "version_id": int(ver_id),
                "mix_path": rd.get('out_path'),
            })
            diag = r.structured_content
            if hasattr(diag, "model_dump"):
                diag = diag.model_dump()
            flagged = diag.get("flagged", diag.get("windows", []))
            n_flags = len(flagged) if isinstance(flagged, list) else flagged
            print(f"  Diagnostics: flagged={n_flags} windows")
        except Exception as e:
            print(f"  Diagnostics skipped: {e}")

        from app.domain.performance.auto_fix import AutoFixPlan, Defect, DefectType
        plan = AutoFixPlan(defects=[])
        plan.generate_fixes()
        print(f"  AutoFix: {len(plan.fixes)} potential fixes (dry run)")

    # ── Summary ──
    print("\n" + "=" * 70)
    print("FULL PIPELINE COMPLETE")
    print(f"  Set #{set_id}, Version {ver_id}")
    print(f"  Tools used: energy_arc + subgenre_preset + filter_sweep + echo +")
    print(f"    reverb + key_compatibility + cue_points + render_mixdown(extended)")
    print(f"    + render_diagnose + auto_fix")
    print(f"  Track count: {len(ga_order)}")
    print(f"  Effects: acid_squelch filter + industrial_stutter echo +")
    print(f"    industrial_warehouse reverb (20% wet)")
    print(f"  Subgenre: industrial_techno (aggressive compression, fast transitions)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
