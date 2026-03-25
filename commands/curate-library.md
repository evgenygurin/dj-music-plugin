---
name: curate-library
description: Classify tracks by mood/subgenre, audit quality, distribute to subgenre playlists, get stats
argument-hint: "[action] [playlist_name]"
---

Curate the DJ library. Use the `curate-library` skill for the full workflow.

Actions:
- `classify` — classify tracks by 15 techno subgenres
- `audit` — audit playlist quality (BPM, key, energy coverage)
- `distribute` — distribute tracks to subgenre playlists
- `stats` — library statistics overview

Examples:
- `/curate-library` — interactive curation workflow
- `/curate-library classify "Peak Time Techno"` — classify tracks in playlist
- `/curate-library stats` — show library statistics
