---
name: build-set
description: "This skill should be used when the user asks to \"build a DJ set\", \"create a set from playlist\", \"optimize track order\", \"rebuild set\", \"reorder tracks\", or \"make a set\". Covers the full workflow from playlist audit to set optimization and review."
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
   - `rebuild_set(set_id=..., pin_tracks=[...], exclude_tracks=[...])` to re-optimize
   - `compare_set_versions(set_id=...)` to verify improvement

7. **Finalize**
   - `get_set_cheat_sheet(set_id=...)` for printable transition guide
   - Suggest `/deliver-set` when user is happy with the result

## Key Parameters

- **algorithm**: `"ga"` (genetic algorithm, better) or `"greedy"` (fast)
- **pinned_tracks**: track IDs that MUST stay in the set
- **excluded_tracks**: track IDs banned from the set
- **dry_run**: `true` to preview without saving

## Tips

- Always audit before building — missing audio features = bad optimization
- GA with 100+ tracks can take 30-120 seconds
- The `view` parameter controls response size: use `"summary"` for overview, `"transitions"` for detail
- Energy arc from template guides the optimizer — tracks are placed to match target energy curve
