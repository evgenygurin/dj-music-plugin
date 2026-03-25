---
name: ym-sync
description: Sync playlists with Yandex Music — push, pull, search, manage YM playlists and likes
argument-hint: "[action] [playlist_name]"
---

Yandex Music sync. Use the `ym-sync` skill for the full workflow.

Actions:
- `sync` — bidirectional playlist sync
- `push` — push local playlist to YM
- `pull` — pull YM playlist to local
- `search` — search YM catalog

Examples:
- `/ym-sync` — interactive sync workflow
- `/ym-sync push "Friday Night Set"` — push set to YM
- `/ym-sync search "Amelie Lens"` — search YM catalog
