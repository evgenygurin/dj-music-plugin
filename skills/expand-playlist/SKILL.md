---
name: expand-playlist
description: "This skill should be used when the user asks to \"expand playlist\", \"find similar tracks\", \"add more tracks\", \"discover new tracks\", \"import from Yandex Music\", or \"fill gaps in playlist\". Covers discovery, import, download, and analysis of new tracks."
---

# Expand Playlist Workflow

Guide the user through discovering and importing new tracks to fill playlist gaps.

## Steps

1. **Audit current playlist**
   - `audit_playlist(playlist_id=..., check="all")` — full quality check
   - Report: track count, BPM distribution, key coverage, subgenre balance
   - Identify gaps: missing subgenres, narrow BPM range, low energy variety

2. **Find similar tracks**
   - For each gap, pick a representative track and run:
     `find_similar_tracks(track_id=..., strategy="combined", limit=10)`
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
