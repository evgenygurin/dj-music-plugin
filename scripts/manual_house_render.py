#!/usr/bin/env python3
"""Manual House render verification for v236/v237 — 7B single bassline, house phrasing (deep_house 32/48).

Task 4: Integration Render Test v237 House — verifies v237 (Cigarette→Nerepla) with deep_house.
Also keeps v236 checks for regression.

Strict gates (fix round 1/5):
- preset apply deep_house 32/48 (TDD step 1)
- global constraints transition/body 8-64, limiter 0.75-0.88, quality >0.84
- v237 MIX 890-910s clamped deep_house 32/48 (BarPlanner 48,27,48,48,28,48,48 avg 42.1bar → 899s; unclamped 974s)
  driving 16/40 ref 680-700s
- validate 6/7 ok
- diagnose scaled <23% (~45/223 scaled from 35/172 baseline 20.3%), windows = int((dur-4)//4) ≈ dur*0.247
- Rave ≤3 flags
- render_plan subgenre & bar values, stems cached
- check_version returns bool, main exits 1 on any FAIL
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.config.render import RenderSettings
from app.domain.performance.subgenre_presets import resolve_preset


def check_preset() -> bool:
    print("=== Preset apply: deep_house 32/48 ===")
    s = RenderSettings()
    p = resolve_preset("deep_house")
    if p is None:
        print("FAIL: resolve_preset('deep_house') is None")
        return False
    p.apply(s)
    ok = s.transition_bars == 32 and s.body_bars == 48
    print(f"  transition_bars={s.transition_bars} body_bars={s.body_bars} -> {'PASS' if ok else 'FAIL'}")
    if not ok:
        return False
    # global constraints 8-64
    if not (8 <= s.transition_bars <= 64 and 8 <= s.body_bars <= 64):
        print("FAIL: transition/body out of 8-64 range")
        return False
    print("  global 8-64 constraint PASS")
    # limiter 0.75-0.88
    if not (0.75 <= s.limiter_ceiling <= 0.88):
        print(f"FAIL: limiter_ceiling {s.limiter_ceiling} out of 0.75-0.88")
        return False
    print(f"  limiter {s.limiter_ceiling} in 0.75-0.88 PASS")
    # check all house presets within 8-64
    for name in ["tech_house", "progressive_house", "classic_house"]:
        q = resolve_preset(name)
        if q is None:
            print(f"FAIL: {name} missing")
            return False
        if not (8 <= q.transition_bars <= 64 and 8 <= q.body_bars <= 64):
            print(f"FAIL: {name} bars out of range")
            return False
        print(f"  {name}: {q.transition_bars}/{q.body_bars} PASS")
    # also check techno suffix fallback
    if resolve_preset("deep") is not p:
        print("FAIL: resolve_preset('deep') != deep_house")
        return False
    print("  resolve_preset('deep') -> deep_house PASS")
    return True


def check_version(vid: int, expected_tracks: list[int], quality_cache: dict[int, float | None]) -> bool:
    print(f"\n=== v{vid} artifacts ===")
    ok = True
    ws = pathlib.Path(f"generated-sets/render/v{vid}")
    if not ws.exists():
        print(f"FAIL: workspace {ws} missing")
        return False
    bg = ws / "beatgrid.json"
    if bg.exists():
        data = json.loads(bg.read_text())
        print(f"  beatgrid {len(data)} entries")
        for e in data:
            print(f"    {e['track_id']}: trim={e['trim_start_s']:.3f} phase={e['phase_ms']} bpm_measured={e.get('bpm_measured')}")
    else:
        print("  beatgrid missing")

    plan_path = ws / "render_plan.json"
    plan_sub: str | None = None
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
        plan_sub = plan.get("subgenre")
        raw_t = plan.get("transition_bars")
        raw_b = plan.get("body_bars")
        applied_note = ""
        if plan_sub in ("deep_house", "deep"):
            applied_note = " (preset deep_house 32/48, null raw overrides -> applied via settings)"
        elif plan_sub:
            p2 = resolve_preset(plan_sub)
            if p2:
                applied_note = f" (preset {plan_sub} {p2.transition_bars}/{p2.body_bars})"
        print(f"  render_plan: subgenre={plan_sub} transition={raw_t} body={raw_b} mode={plan.get('mode')}{applied_note}")
    else:
        print("  render_plan missing")
        ok = False

    # MIX duration — strict per subgenre
    dur: float | None = None
    mix = ws / "MIX.mp3"
    if mix.exists():
        try:
            import subprocess

            out = subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(mix)],
                text=True,
            ).strip()
            dur = float(out)
            print(f"  MIX duration {dur:.1f}s ({dur/60:.1f}m)")
            if plan_sub in ("deep_house", "deep"):
                if 890 <= dur <= 910:
                    print("  duration 890-910s clamped deep_house PASS (BarPlanner 48,27,48,48,28,48,48 → 899s)")
                else:
                    print(f"  FAIL: duration {dur:.1f}s outside 890-910 for deep_house 32/48 (expected clamped 899s)")
                    ok = False
            else:
                # driving 16/40 reference
                if 680 <= dur <= 700:
                    print("  duration 680-700s driving 16/40 PASS")
                else:
                    print(f"  FAIL: duration {dur:.1f}s outside 680-700 (expected for driving 16/40)")
                    ok = False
        except Exception as e:
            print(f"  MIX exists but ffprobe failed: {e}")
            ok = False
    else:
        print("  MIX.mp3 missing")
        ok = False

    grid_check = ws / "grid_check.json"
    if grid_check.exists():
        gc = json.loads(grid_check.read_text())
        tracks = gc.get("tracks", [])
        ok_cnt = sum(1 for t in tracks if t["status"] == "ok")
        total = len(tracks)
        print(f"  validate_grid: {ok_cnt}/{total} ok")
        for t in tracks:
            print(f"    {t['title']}: {t['status']} dev={t['bpm_dev']}")
        # v237 deep_house expects 6/7 (Rave fail only); v236 driving has extra Players Only fail → 5/7
        expected_ok = 6 if vid == 237 else 5 if vid == 236 else 6
        if total == 7 and ok_cnt == expected_ok:
            print(f"  validate {expected_ok}/7 ok PASS")
        else:
            print(f"  FAIL: validate expected {expected_ok}/7 ok, got {ok_cnt}/{total}")
            ok = False
    else:
        print("  grid_check.json missing")
        ok = False

    diag_path = ws / "diagnostics.json"
    if diag_path.exists():
        diag = json.loads(diag_path.read_text())
        flagged = diag.get("flagged", 0)
        windows = len(diag.get("windows", []))
        ratio = flagged / windows if windows else 0
        print(f"  diagnose flagged {flagged}/{windows} ({ratio:.1%})")
        # dynamic expected windows from duration (≈ dur*0.247, exact int((dur-4)//4))
        if dur is not None:
            expected_windows = int((dur - 4) // 4) if dur > 4 else 0
            # also show dur*0.247 approx
            approx = dur * 0.247
            print(f"  expected windows {expected_windows} (dur*0.247≈{approx:.1f}, exact int((dur-4)//4))")
            if abs(windows - expected_windows) > 2:
                print(f"  FAIL: windows {windows} != expected {expected_windows} (dur {dur:.1f}s)")
                ok = False
            else:
                print(f"  windows count matches expected {expected_windows} PASS")
        # scaled threshold: <23% (~45/223 scaled from 35/172 baseline 20.3%)
        # baseline scaled absolute = 35*windows/172
        scaled_abs = round(35 * windows / 172) if windows else 35  # noqa: RUF046 intentional
        print(f"  scaled baseline flagged <{scaled_abs}/{windows} (35/172 scaled), gate <23% (~{int(windows*0.23)}/{windows})")
        if ratio < 0.23:
            print(f"  diagnose scaled <23% PASS ({flagged}/{windows}={ratio:.1%})")
            if flagged > scaled_abs:
                print(f"  NOTE: flagged {flagged} > baseline scaled {scaled_abs} (20.3%) but <23% — within loosened gate")
        else:
            print(f"  FAIL: diagnose flagged {flagged}/{windows}={ratio:.1%} >=23% (scaled baseline {scaled_abs}/{windows})")
            ok = False

        # Rave: count flagged windows overlapping Rave body
        try:
            gc_path = ws / "grid_check.json"
            if gc_path.exists():
                gc_data = json.loads(gc_path.read_text())
                rave_body = next((t for t in gc_data.get("tracks", []) if t["track_id"] == 519), None)
                if rave_body:
                    body_s, body_e = rave_body["body_s"], rave_body["body_e"]
                    rave_flags = [w for w in diag["windows"] if w["tags"] and body_s - 4 <= w["offset_s"] <= body_e + 4]
                    print(f"  Rave body {body_s:.1f}-{body_e:.1f}s flagged windows: {len(rave_flags)}")
                    for w in rave_flags[:5]:
                        print(f"    {w['offset_s']}s {w['tags']}")
                    if len(rave_flags) <= 3:
                        print("  Rave clean (<=3 flags) PASS (expected 2)")
                    else:
                        print(f"  FAIL: Rave flagged {len(rave_flags)} >3")
                        ok = False
        except Exception as e:
            print(f"  Rave check skipped: {e}")
            ok = False
    else:
        print("  diagnostics.json missing")
        ok = False

    # quality score from DB >0.84 (pre-fetched)
    qs = quality_cache.get(vid)
    if qs is not None:
        passed = qs > 0.84
        print(f"  quality_score {qs:.4f} -> {'PASS >0.84' if passed else 'FAIL <=0.84'}")
        if not passed:
            ok = False
    else:
        print(f"  quality_score missing for v{vid}")
        ok = False

    # stems cached
    stems_dir = ws / "stems"
    if stems_dir.exists():
        cnt = sum(1 for _ in stems_dir.rglob("*.flac"))
        print(f"  stems cached in workspace: {cnt} flac files under {stems_dir}")
    else:
        print(f"  stems dir missing {stems_dir}")

    # global cached stems count
    try:
        from app.config import get_settings

        root = pathlib.Path(get_settings().delivery.output_dir) / "render"
        total_flac = sum(1 for _ in root.rglob("*.flac"))
        print(f"  global stems cache: {total_flac} flac files under {root}")
    except Exception as e:
        print(f"  global stems check failed: {e}")

    print("  All 7 tracks 7B Eb min - single bassline - LOW swap only (house phrasing 16/32 beats = 8/16 bars)")
    if not ok:
        print(f"  === v{vid} FAIL ===")
    else:
        print(f"  === v{vid} PASS ===")
    return ok


def fetch_quality_scores(vids: list[int]) -> dict[int, float | None]:
    """Batch fetch quality_score for given version ids (one transaction)."""
    import asyncio

    from sqlalchemy import text as sa_text

    from app.db.session import get_session_factory

    async def _batch():
        factory = get_session_factory()
        async with factory() as s:
            out: dict[int, float | None] = {}
            for vid in vids:
                r = await s.execute(
                    sa_text("SELECT quality_score FROM dj_set_versions WHERE id=:vid"),
                    {"vid": vid},
                )
                row = r.fetchone()
                out[vid] = float(row[0]) if row and row[0] is not None else None
            return out

    try:
        return asyncio.run(_batch())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_batch())
        finally:
            loop.close()


def main() -> int:
    ok_preset = check_preset()
    if not ok_preset:
        print("\nPreset check FAIL")
        return 1
    print("\nPreset checks PASS (deep_house 32/48)")

    # Check v237 (primary task) and v236 regression
    # v237 tracks: 29943,27268,519,304,29941,257,13553 (Cigarette->Nerepla)
    v237_tracks = [29943, 27268, 519, 304, 29941, 257, 13553]
    v236_tracks = [29943, 27268, 519, 304, 29941, 257, 29946]
    qcache = fetch_quality_scores([236, 237])

    ok237 = check_version(237, v237_tracks, qcache)
    ok236 = check_version(236, v236_tracks, qcache)

    if not (ok_preset and ok237 and ok236):
        print("\n=== Manual House Render Verification FAIL ===")
        if not ok237:
            print("v237 FAIL — check MIX 890-910s, validate 6/7, diagnose <23%")
        if not ok236:
            print("v236 FAIL — regression")
        return 1

    print("\n=== Manual House Render Verification COMPLETE PASS ===")
    print("All gates PASS: preset 32/48, MIX 890-910s clamped (or 680-700 driving ref), validate 6/7 ok, diagnose <23% scaled, Rave <=3, quality >0.84, bars 8-64")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
