---
name: expand-playlist
description: "Use when the user asks to expand a playlist, find similar tracks, add more tracks, discover new tracks, import from Yandex Music, or fill gaps in a playlist. Covers discovery, feedback gating, import, download and analysis."
version: 1.0.1
---

# Expand Playlist Workflow

Guide the user through discovering and importing new tracks via the v1 polymorphic dispatchers. See @docs/tool-catalog.md (13 dispatchers + 27 resources + 6 prompts).

## Quick Path (one-call)

Use the `expand_playlist_workflow` prompt — it chains audit → discover → feedback gate → import → download → analyze → classify:
```text
expand_playlist_workflow(source_playlist_id=<id>, target_count=100, genre_filter=["techno"], dry_run=true)
```

Run once with `dry_run=true` to preview, then again without it.

## Granular Path (step-by-step)

1. **Audit current playlist**
   - Read `local://playlists/{id}/audit` — full quality check, gap report, BPM/key/subgenre coverage

2. **Find similar tracks (YM recommendations)** per seed:
   - `provider_read(provider="yandex", entity="track_similar", id=<ym_track_id>, params={"limit": 20})`
   - For free-text search: `provider_search(provider="yandex", query="Amelie Lens acid techno", type="tracks", limit=20)`
   - LLM-driven discovery lives in the `expand_playlist_workflow` prompt (it asks Claude for search queries, then feeds them to `provider_search`) — see @.claude/rules/llm-sampling.md

3. **Filter candidates by feedback** (dedupe / drop disliked / boost liked)
   - Known tracks already in DB: `entity_list(entity="track", filters={"external_id__in": [...]}, fields="summary")` — anything returned is already imported
   - Feedback history: `entity_list(entity="track_feedback", filters={"ym_track_id__in": [...]}, fields="full")`
   - Let Claude decide which to import, which to skip.

4. **Review candidates**
   - Present found tracks with BPM / key / energy if available
   - For extra detail: `provider_read(provider="yandex", entity="track", id=<ym_id>)`

5. **Import selected tracks**
   - `entity_create(entity="track", data={"ym_ids": ["12345", "67890"], "playlist_id": <pid>})`
     (handler `track_import` fetches metadata from YM, creates `Track` + `YandexMetadata` + `RawProviderResponse`, links to playlist)

6. **Download MP3s** (needed for DJ software / L4 delivery)
   - `entity_create(entity="audio_file", data={"track_ids": [...], "persistent": true})`
     (handler `audio_file_download` — writes to `DJ_YM_LIBRARY_PATH`, links `DjLibraryItem`, idempotent)

7. **Analyze new tracks** (L1+L2 — mood classification lands in features)
   - `entity_create(entity="track_features", data={"track_ids": [...], "level": 2})`
   - For full scoring-ready L3: `level=3`; for L4 structure: `level=4`.
   - Re-analyze at a higher level: `entity_update(entity="track_features", id=<fid>, data={"level": 3})`

8. **Re-audit**
   - Read `local://playlists/{id}/audit` again — compare coverage before / after

## Full Expansion Pipeline

End-to-end chain via prompt (audit → discover → import → download → analyze → classify → distribute):
```text
full_pipeline(source_playlist_id=<id>, target_per_subgenre=40)
```

## Tips

- `provider_search` and `provider_read` are in the `provider:read` namespace — visible by default; no unlock needed
- `entity_create(entity="track", ...)` covers import; `entity_create(entity="audio_file", ...)` covers download; `entity_create(entity="track_features", ...)` covers analysis — three separate side-effect handlers, not one monolith
- Always download before `deliver_set` — iCloud stubs (<90% size) cannot be copied
- For scoring-heavy expansion (pick top-N by candidate compatibility), use `transition_score_pool(track_ids=[...])`
- Tool reference: @docs/tool-catalog.md; @.claude/rules/llm-sampling.md for client-driven discovery
