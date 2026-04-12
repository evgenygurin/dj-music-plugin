---
name: build-set
description: "Use when the user asks to build a DJ set, create a set from playlist, optimize track order, rebuild set, reorder tracks, or make a set. Covers playlist audit, GA/greedy optimization, review and iteration."
version: 0.7.1
---

# Build DJ Set Workflow

Guide the user through building an optimized DJ set from a playlist.

## Steps

1. **Identify source playlist**
   - Ask which playlist to use, or list available playlists via `list_playlists`
   - If user mentions a name, resolve via `get_playlist(query="...")`

2. **Choose template and parameters**
   - Show available templates (8 options):
     - `warm_up_30` (30 min, low energy opener)
     - `classic_60` (60 min, standard build-peak-release)
     - `peak_hour_60` (60 min, high energy throughout)
     - `roller_90` (90 min, sustained driving energy)
     - `progressive_120` (120 min, gradual build)
     - `wave_120` (120 min, multiple energy waves)
     - `closing_60` (60 min, wind-down)
     - `full_library` (use all tracks)
   - Ask for target duration if not using template default
   - Ask for BPM range preferences

3. **Audit source playlist first**
   - Run `audit_playlist(playlist_id=..., template=...)` to check quality
   - Report: total tracks, tracks with features, BPM/key/energy coverage
   - If too few tracks or missing features, suggest `analyze_batch` first

4. **Build the set**
   - Use `build_set(playlist_id=..., name=..., template=..., algorithm="ga")`
   - GA optimizer is default — better results but slower (~30s)
   - Use `algorithm="greedy"` only if user wants speed over quality

5. **Review the result**
   - Run `quick_set_review(set_id=...)` for instant quality overview
   - Show: total score, hard conflicts, weak transitions, energy arc match
   - If hard conflicts exist, suggest `rebuild_set` with problematic tracks excluded

6. **Iterate if needed**
   - `suggest_next_track(set_id=..., after_position=N)` for gap filling
   - `find_replacement(set_id=..., position=N)` for weak transitions
   - `rebuild_set(set_id=..., pin_tracks=[...], exclude_tracks=[...], algorithm="ga", version_label="...")` — creates a new version
   - `compare_set_versions(set_id=...)` to verify improvement

7. **Finalize**
   - `get_set_cheat_sheet(set_id=...)` for printable transition guide
   - Suggest `/deliver-set` when user is happy with the result

## Key Parameters

- **algorithm**: `"ga"` (genetic algorithm, better) or `"greedy"` (fast, default). Without features, falls back to `playlist_order`.
- **rebuild_set params**: `pin_tracks: list[int]`, `exclude_tracks: list[int]`, `algorithm`, `version_label` — produces a new `SetVersion`, never mutates the previous one.
- **dry_run**: `true` to preview without saving — supported by `build_set` only (not `rebuild_set`).
- **view** (get_set): `summary | tracks | transitions | full`

Auto-analysis: `build_set` triggers L3 analysis for any candidate track with `analysis_level < 3` — no manual `analyze_track` needed (see @docs/reports/tiered-analysis-design-2026-03-27.md).

## Tips

- Audit before building — missing audio features force `playlist_order` fallback
- GA with 100+ tracks can take 30-120 seconds (tool timeout: 120s)
- Use `view="summary"` for overview, `view="transitions"` for transition detail
- Energy arc from template guides the optimizer — tracks are placed to match target energy curve
- Tool reference: @docs/tool-catalog.md (build_set, rebuild_set, score_transitions, suggest_next_track, find_replacement, compare_set_versions, quick_set_review, get_set_cheat_sheet)
