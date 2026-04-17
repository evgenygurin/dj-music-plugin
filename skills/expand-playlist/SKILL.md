---
name: expand-playlist
description: "Use when the user asks to expand a playlist, find similar tracks, add more tracks, discover new tracks, import from Yandex Music, or fill gaps in a playlist. Covers discovery, feedback gating, import, download and analysis."
version: 0.8.2
---

# Expand Playlist Workflow

Guide the user through discovering and importing new tracks to fill playlist gaps.

## Quick Path (one-call)

Use `expand_platform_playlist` for automated expansion against a platform playlist:
```text
expand_platform_playlist(playlist_id="1234", target_count=100, genre_filter=["techno"], dry_run=true)
```

Note: use `playlist_id` (opaque remote playlist ID). Run with `dry_run=true` first to preview, then re-run without it.

## Granular Path (step-by-step)

1. **Audit current playlist**
   - `audit_playlist(playlist_id=...)` — full quality check
   - Report: track count, BPM distribution, key coverage, subgenre balance

2. **Find similar tracks** (per seed)
   - `find_similar_tracks(track_id=..., strategy="ym", limit=20, genre_filter=["techno"], genre_blacklist=["pop"], exclude_patterns=["remix", "edit"])`
   - `strategy`: `"ym"` (default, free) or `"llm"` (you generate `search_queries` from seed track's mood/energy/subgenre — requires `DJ_ANTHROPIC_API_KEY` for server-side fallback or a sampling-capable client)
   - Filters: `genre_filter`, `genre_blacklist`, `exclude_patterns`, `min_duration_ms`, `max_duration_ms`

3. **Filter by feedback** (drop disliked, mark liked)
   - `filter_by_feedback(ym_track_ids=["12345", "67890"])`
   - Returns three buckets: `passed` (unknown), `blocked` (disliked), `boosted` (liked) — Claude decides what to import

4. **Review candidates**
   - Present found tracks with BPM, key, energy info
   - For manual lookups: `search_platform(query="...", type="tracks")`

5. **Import selected tracks**
   - `import_tracks(track_refs=[...], playlist_id=..., auto_analyze=true)`
   - Creates local track records, links YM metadata, optionally queues analysis

6. **Download MP3s** (needed for DJ software / L4 delivery)
   - `download_tracks(track_refs=[...], skip_existing=true)`
   - Writes to `DJ_YM_LIBRARY_PATH`; auto-links files to tracks via `DjLibraryItem`
   - Accepts YM IDs (>=100000) or local IDs (<100000) — auto-resolved

7. **Analyze new tracks** (if `auto_analyze=false`)
   - `unlock_tools(action="unlock", category="audio")`
   - `analyze_batch(playlist_id=..., analyzers=["bpm", "key", "loudness", "energy", "spectral"])`

8. **Re-audit**
   - `audit_playlist(playlist_id=...)` — compare before/after coverage

## Full Expansion Pipeline

For end-to-end expansion, use the workflow prompt (audit → discover → import → download → analyze → classify → distribute):
```text
full_expansion_pipeline source_playlist="TECHNO FOR DJ SETS" target_per_subgenre=40
```

## Tips

- `strategy="ym"` is the fast/free path; `"llm"` requires `DJ_ANTHROPIC_API_KEY` or a sampling-capable client
- `filter_tracks(exclude_set_id=N)` finds tracks not yet in a given set — useful for picking imports
- Always download before `deliver_set` — iCloud stubs (<90% size) cannot be copied
- Tool reference: @docs/tool-catalog.md (find_similar_tracks, filter_by_feedback, expand_platform_playlist, import_tracks, download_tracks)
