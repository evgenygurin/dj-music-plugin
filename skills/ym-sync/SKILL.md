---
name: ym-sync
description: "This skill should be used when the user asks to \"sync playlist\", \"push to YM\", \"pull from YM\", \"yandex music search\", \"ym playlist\", or \"manage YM likes\". Covers bidirectional Yandex Music sync, playlist management, search, and likes."
version: 0.5.0
---

# Yandex Music Sync Workflow

Guide the user through syncing local playlists with Yandex Music.

## Unlock YM Tools First

YM tools are in the extended category. Unlock if needed:
```text
unlock_tools(action="unlock", category="ym")
```

## Sync Actions

### Search YM
- `ym_search(query="...", type="track")` — search tracks
- `ym_search(query="...", type="all")` — search everything
- Types: `track`, `album`, `artist`, `playlist`, `all`

### Get Track Info
- `ym_get_tracks(track_ids=["12345", "67890"])` — batch fetch
- `ym_get_album(album_id=..., include_tracks=true)` — album with tracks
- `ym_artist_tracks(artist_id=..., page=0)` — paginated artist tracks

### Playlist Management
- `ym_playlists(action="list")` — list user's YM playlists
- `ym_playlists(action="get", playlist_id="...")` — get playlist tracks
- `ym_playlists(action="create", name="...", visibility="public")` — create new
- `ym_playlists(action="add_tracks", playlist_id="...", track_ids=[...])` — add tracks
- `ym_playlists(action="remove_tracks", playlist_id="...", positions=[...])` — remove by position

### Likes
- `ym_likes(action="get_liked")` — get liked track IDs
- `ym_likes(action="add", track_ids=[...])` — like tracks
- `ym_likes(action="remove", track_ids=[...])` — unlike

### Bidirectional Sync
- `sync_playlist(playlist_id=..., direction="pull")` — pull YM → local
- `sync_playlist(playlist_id=..., direction="push")` — push local → YM
- `conflict_strategy="ask"` — ask for each conflict (default)
- `conflict_strategy="source_wins"` — source of truth wins silently
- `dry_run=true` — preview changes

### Push DJ Set to YM
- `push_set_to_ym(set_id=..., ym_playlist_name="My DJ Set")` — create/update YM playlist
- `mode="overwrite"` / `"append"` / `"create_new"`

## Source of Truth

Each playlist has a `source_of_truth`:
- `"local"` — local DB is authoritative, push changes to YM
- `"yandex"` — YM is authoritative, pull changes to local

Sync direction follows source of truth by default.

## YM API Quirks

- **Rate limiting**: 1.5s between calls + exponential backoff on 429
- **Playlist edits use diff format**: the server handles this internally
- **After every edit**: server re-fetches for fresh revision
- **Broken endpoints**: artist brief-info (403), lyrics (400) — skipped

## Tips

- Always `sync_playlist` before building sets from YM-sourced playlists
- Use `dry_run=true` first to see what would change
- Batch operations (get_tracks, get_albums) are more efficient than one-by-one
- Track IDs are strings in YM (not integers)
