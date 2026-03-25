---
name: expand-playlist
description: Expand a playlist with similar tracks from Yandex Music — discover, import, download, analyze
argument-hint: "[playlist_name] [target_count]"
---

Expand a playlist with new tracks. Use the `expand-playlist` skill for the full workflow.

Arguments (all optional):
- `playlist_name` — playlist to expand (will prompt if not given)
- `target_count` — target number of tracks after expansion

Examples:
- `/expand-playlist` — interactive expansion workflow
- `/expand-playlist "TECHNO FOR DJ SETS" 100` — expand to 100 tracks
