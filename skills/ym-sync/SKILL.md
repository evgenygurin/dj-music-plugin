---
name: ym-sync
description: "Use when the user asks to sync a playlist, push or pull from Yandex Music, search platform catalog, manage platform playlists, or manage liked tracks. Covers bidirectional sync, playlist management, search and likes."
version: 0.8.1
---

# Yandex Music Sync Workflow

Guide the user through syncing local playlists with Yandex Music.

## Unlock Platform Tools First

Platform tools are in the extended category. Unlock if needed:
```text
unlock_tools(action="unlock", category="platform")
```

## Sync Actions

### Search Platform
- `search_platform(query="...", type="tracks")` — search tracks (note: plural form, see @.claude/rules/ym.md)
- `search_platform(query="...", type="all")` — search everything
- Types: `tracks`, `albums`, `artists`, `playlists`, `all`

### Get Track Info
- `get_platform_tracks(track_ids=["12345", "67890"])` — batch fetch
- `get_platform_album(album_id=..., include_tracks=true)` — album with tracks
- `get_platform_artist_tracks(artist_id=..., offset=0, limit=20)` — paginated artist tracks

### Playlist Management

`platform_playlists` is action-dispatched. Identify a playlist by `playlist_id` (remote provider ID). Mutating actions need a fresh `revision`.

- `platform_playlists(action="list")` — list user's platform playlists
- `platform_playlists(action="get", playlist_id="1234")` — get playlist metadata
- `platform_playlists(action="get_tracks", playlist_id="1234")` — get playlist tracks (id/title/artists)
- `platform_playlists(action="create", name="My Set")` — create new playlist
- `platform_playlists(action="rename", playlist_id="1234", name="New name")`
- `platform_playlists(action="delete", playlist_id="1234")`
- `platform_playlists(action="add_tracks", playlist_id="1234", track_ids=["t1", "t2"], revision=N)` — bare track IDs; album resolution happens server-side
- `platform_playlists(action="remove_tracks", playlist_id="1234", track_ids=["t1"])` — removes by track_id (not by position)

### Likes
- `platform_liked_tracks(action="get_liked")` — get liked track IDs
- `platform_liked_tracks(action="add", track_ids=[...])` — like tracks
- `platform_liked_tracks(action="remove", track_ids=[...])` — unlike

### Bidirectional Sync
- `sync_playlist(playlist_id=..., direction="pull")` — pull YM → local (default)
- `sync_playlist(playlist_id=..., direction="push")` — push local → YM
- `conflict_strategy="source_wins"` (default) — source of truth wins silently
- `dry_run=true` (default) — preview changes; pass `false` to apply

### Push DJ Set to Platform
- `push_set_to_platform(set_id=..., platform_playlist_name="My DJ Set", mode="auto")`
- `mode` ∈ `{create, update, auto}` — `auto` updates an existing remote playlist with the same name, otherwise creates one

## Source of Truth

Each playlist has a `source_of_truth`:
- `"local"` — local DB is authoritative, push changes to YM
- `"yandex"` — YM is authoritative, pull changes to local

Sync direction follows source of truth by default.

## YM API Quirks

See @docs/ym-api-guide.md for full details. Highlights:

- **Rate limiting**: 1.5s between calls + exponential backoff on 429
- **Playlist edits use diff format**: handled inside the client
- **`revision` is required** for `add_tracks` — fetch it via `platform_playlists(action="get", playlist_id=...)` first
- **Broken endpoints**: artist brief-info (403 Antirobot), lyrics (400 HMAC) — skipped

## Tips

- Always `sync_playlist` before building sets from YM-sourced playlists
- Use `dry_run=true` first to see what would change
- Batch operations (get_tracks, get_albums) are more efficient than one-by-one
- Track IDs are strings in YM (not integers)
