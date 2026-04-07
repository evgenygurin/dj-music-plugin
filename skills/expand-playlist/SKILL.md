---
name: expand-playlist
description: "This skill should be used when the user asks to \"expand playlist\", \"find similar tracks\", \"add more tracks\", \"discover new tracks\", \"import from Yandex Music\", or \"fill gaps in playlist\". Covers discovery, import, download, and analysis of new tracks."
version: 0.5.0
---

# Expand Playlist Workflow

Guide the user through discovering and importing new tracks to fill playlist gaps.

## Quick Path (one-call)

Use `expand_playlist_ym` for automated expansion:
```text
expand_playlist_ym(ym_playlist_kind=..., target_count=100, genre_filter=["techno"], dry_run=true)
```

Then review candidates and run without dry_run to add.

## Granular Path (step-by-step)

1. **Audit current playlist**
   - `audit_playlist(playlist_id=..., check="all")` — full quality check
   - Report: track count, BPM distribution, key coverage, subgenre balance

2. **Find similar tracks**
   - `find_similar_tracks(track_id=..., genre_filter=["techno"], limit=20)` — per track
   - Or `expand_playlist_ym(..., dry_run=true)` — batch from all seeds

3. **Filter by feedback**
   - `filter_by_feedback(ym_track_ids=[...])` — block disliked, boost liked
   - Strategies:
     - `"ym"` — Yandex Music recommendations (fast, requires YM IDs)
     - `"llm"` — AI-assisted search queries (creative, needs sampling)
     - `"combined"` — both approaches merged (best results)
   - Filter by: `bpm_tolerance`, `key_compatible`

3. **Review candidates**
   - Present found tracks with BPM, key, energy info
   - Let user pick which to import
   - Use `ym_search(query="...", type="track")` for manual searches

4. **Import selected tracks**
   - `import_tracks(track_refs=[...], playlist_id=..., auto_analyze=true)`
   - This creates local track records and links YM metadata
   - `auto_analyze=true` queues audio analysis automatically

5. **Download MP3s** (if needed for DJ software)
   - `download_tracks(track_refs=[...])` — downloads from YM to iCloud library
   - Uses path from `DJ_YM_LIBRARY_PATH` env var
   - Skips already-downloaded files with `skip_existing=true`

6. **Analyze new tracks** (if auto_analyze wasn't used)
   - Unlock audio tools: `unlock_tools(action="unlock", category="audio")`
   - `analyze_batch(playlist_id=..., analyzers=["bpm", "key", "loudness", "energy", "spectral"])`
   - This enables proper transition scoring for the new tracks

7. **Re-audit**
   - `audit_playlist(playlist_id=...)` — verify gaps are filled
   - Compare before/after coverage

## Full Expansion Pipeline

For comprehensive expansion, run the complete workflow prompt:
```text
Use the full_expansion_pipeline prompt with:
- source_playlist: "TECHNO FOR DJ SETS"
- target_per_subgenre: 40-50
```

This automates: audit → discover → import → download → analyze → classify → distribute.

## Tips

- Start with `strategy="ym"` — it's fast and free (no API key needed)
- `strategy="llm"` generates creative search queries but needs `ANTHROPIC_API_KEY`
- Always download before building sets — iCloud stubs can't be copied to output
- `filter_tracks(exclude_set_id=N)` finds tracks not yet in a specific set
