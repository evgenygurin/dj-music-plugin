---
name: curate-library
description: "Use when the user wants to classify tracks by mood/subgenre, audit library quality, check playlist health, distribute tracks to subgenre playlists, or get library statistics. Triggers on: 'classify tracks', 'audit playlist', 'library stats', 'distribute subgenres', 'mood classification', 'review library'."
argument-hint: "[action] [playlist_name]"
allowed-tools: ["mcp__*dj-music*"]
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
- `review_set_quality(set_id=...)` — deep quality analysis
- Transition scores, energy arc compliance, subgenre variety
- Identifies weakest transitions and suggests fixes

### Library Statistics
- `get_library_stats()` — overview of entire library
- Total tracks, feature coverage, subgenre distribution
- BPM histogram, key distribution, energy range

### Distribute to Subgenre Playlists
- `distribute_to_subgenres(source_playlist_id=..., mode="add")` — add new tracks
- `distribute_to_subgenres(mode="clean_rebuild")` — full rebuild (asks confirmation)
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

- Run `classify_mood` after importing new tracks — needed for subgenre playlists
- `driving` and `hypnotic` are catch-all subgenres — they get penalized in scoring
- Audit before building sets — ensures enough quality tracks are available
- Use `filter_tracks(mood="peak_time", has_features=true)` to find tracks by subgenre
