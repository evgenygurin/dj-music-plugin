---
name: curate-library
description: "Use when the user asks to classify tracks, audit playlist, get library stats, distribute to subgenres, run mood classification, or review library quality. Covers mood classification, audits, subgenre distribution and stats."
version: 0.8.2
---

# Curate DJ Library Workflow

Guide the user through classifying, auditing, and organizing their techno library.

## Actions

### Classify Tracks by Mood
- `classify_mood(playlist_id=...)` — classify all tracks in a playlist
- `classify_mood(track_ids=[...])` — classify specific tracks
- Returns: mood (1 of 15 subgenres), confidence, reasoning
- Use `reclassify=true` to override existing classifications

**15 Techno Subgenres** (low → high energy):
ambient_dub → dub_techno → minimal → detroit → melodic_deep → progressive → hypnotic → driving → tribal → breakbeat → peak_time → acid → raw → industrial → hard_techno

### Audit Playlist Quality
- `audit_playlist(playlist_id=..., check="all")` — comprehensive audit
- Checks: BPM range, key distribution, energy coverage, missing features
- `audit_playlist(playlist_id=..., template="classic_60")` — check against a template
- Reports gaps and recommendations

### Review Set Quality
- `quick_set_review(set_id=...)` — fast quality overview (transition scores, hard conflicts, energy arc match)
- `analyze_set_narrative(set_id=...)` — deeper narrative + subgenre variety analysis
- Use these to identify weakest transitions before recommending fixes

### Library Statistics
- `get_library_stats()` — overview of entire library
- Total tracks, feature coverage, subgenre distribution
- BPM histogram, key distribution, energy range

### Distribute to Subgenre Playlists
- `distribute_to_subgenres(source_playlist_id=..., mode="append")` — add classified tracks to subgenre playlists (default mode)
- `distribute_to_subgenres(mode="clean_rebuild")` — wipe and rebuild every subgenre playlist from scratch
- `sync_to_ym=true` — also push subgenre playlists to YM
- `dry_run=true` — preview distribution without changes

## Techno Quality Criteria

Tracks must meet these thresholds to be valid techno:

| Parameter | Range |
|-----------|-------|
| BPM | 120-155 |
| LUFS | -20 to -4 |
| Energy mean | ≥ 0.05 |
| Onset rate | ≥ 1.0 |
| Kick prominence | ≥ 0.05 |
| Spectral centroid | 300-10000 Hz |

## Tips

- `classify_mood` auto-triggers L1+L2 analysis for unanalyzed tracks — no need to call `analyze_track` manually
- `driving` and `hypnotic` are catch-all subgenres — penalized via `settings.mood_catch_all_penalty`
- Audit before building sets — ensures enough quality tracks are available
- Use `filter_tracks(mood="peak_time")` to find tracks by subgenre (combine with `bpm_min/max`, `energy_min/max`)
- Domain criteria & quality thresholds: see @REQUIREMENTS.md §12 and @docs/audio-pipeline.md
- Tool reference: @docs/tool-catalog.md (classify_mood, audit_playlist, quick_set_review, analyze_set_narrative, distribute_to_subgenres, get_library_stats)
