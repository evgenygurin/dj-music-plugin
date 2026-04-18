---
name: curate-library
description: "Use when the user asks to classify tracks, audit playlist, get library stats, distribute to subgenres, run mood classification, or review library quality. Covers mood classification, audits, subgenre distribution and stats."
version: 1.0.1
---

# Curate DJ Library Workflow

Guide the user through classifying, auditing, and organizing their techno library via the v1 polymorphic dispatchers (13 tool dispatchers — см. @docs/tool-catalog.md).

## Actions

### Classify Tracks by Mood

Mood classification is a side-effect of the `track_features_analyze` handler — it runs at L1+L2 and writes `mood` / `mood_confidence` into `track_audio_features_computed`.

- Single track / batch at level 2:
  `entity_create(entity="track_features", data={"track_ids": [...], "level": 2})`
- Whole playlist:
  1. Get track IDs: `entity_get(entity="playlist", id=<id>, include_relations=["tracks"])`
  2. `entity_create(entity="track_features", data={"track_ids": [...], "level": 2})`
- Re-classify (override existing):
  `entity_update(entity="track_features", id=<features_id>, data={"level": 2, "force": true})`
  (handler `track_features_reanalyze`)

**15 Techno Subgenres** (low → high energy):
ambient_dub → dub_techno → minimal → detroit → melodic_deep → progressive → hypnotic → driving → tribal → breakbeat → peak_time → acid → raw → industrial → hard_techno

Static reference: read `reference://subgenres`.

### Audit Playlist Quality

- Read `local://playlists/{id}/audit` — BPM range, key distribution, energy coverage, missing features, gap report
- Audit rules reference: read `reference://audit_rules`

### Review Set Quality

- Read `local://sets/{id}/review` — transition scores, energy arc compliance, subgenre variety, weakest transitions + suggested fixes

### Library Statistics

Aggregate directly with `entity_aggregate`:
- Total tracks: `entity_aggregate(entity="track", operation="count")`
- Feature coverage: `entity_aggregate(entity="track_features", operation="count")`
- Subgenre distribution: `entity_aggregate(entity="track_features", operation="group_by", group_by="mood")`
- BPM histogram: `entity_aggregate(entity="track_features", operation="histogram", field="bpm")`
- Key distribution: `entity_aggregate(entity="track_features", operation="group_by", group_by="key_code")`

### Distribute to Subgenre Playlists

There's no single `distribute_to_subgenres` tool in v1 — compose from primitives:

1. Ensure classification: `entity_create(entity="track_features", data={"track_ids": [...], "level": 2})`
2. For each subgenre, select tracks:
   `entity_list(entity="track", filters={"mood": "peak_time"}, fields="summary", limit=500)`
3. Add to the matching local playlist:
   `entity_update(entity="playlist", id=<pl_id>, data={"track_ids_append": [...]})`
4. Push subgenre playlists to YM: `playlist_sync(playlist_id=<pl_id>, direction="push", source="yandex")`
   (namespace `sync` is locked by default — unlock first via `unlock_namespace(namespace="sync", action="unlock")`)
5. For an end-to-end recipe use the `expand_playlist_workflow` or `full_pipeline` prompts.

## Techno Quality Criteria

Tracks must meet these thresholds to be valid techno (see `reference://audit_rules`):

| Parameter | Range |
|-----------|-------|
| BPM | 120–155 |
| LUFS | -20 to -4 |
| Energy mean | ≥ 0.05 |
| Onset rate | ≥ 1.0 |
| Kick prominence | ≥ 0.05 |
| Spectral centroid | 300–10000 Hz |

## Tips

- L1+L2 analysis is triggered automatically by `entity_create(entity="track_features", ...)` — no need to download audio manually; temp download lives inside the handler
- `driving` / `hypnotic` are catch-all subgenres — penalized via `settings.mood_catch_all_penalty`
- Audit before building sets — ensures enough quality tracks are available
- Use Django-style filters on `entity_list(entity="track", filters={...})`: `bpm__gte`, `mood__in`, `energy_mean__between`, `title__icontains`
- Domain criteria & quality thresholds: see @REQUIREMENTS.md §12 and @docs/audio-pipeline.md
- Tool reference: @docs/tool-catalog.md (13 dispatchers + 27 resources + 6 prompts)
