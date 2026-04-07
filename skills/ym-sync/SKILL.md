---
name: ym-sync
description: "Use when the user asks to sync a playlist, push or pull from Yandex Music, search YM, manage YM playlists, or manage YM likes. Covers bidirectional sync, playlist management, search and likes."
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
- `ym_search(query="...", type="tracks")` — search tracks (note: plural form, see @.claude/rules/ym.md)
- `ym_search(query="...", type="all")` — search everything
- Types: `tracks`, `albums`, `artists`, `playlists`, `all`

### Get Track Info
- `ym_get_tracks(track_ids=["12345", "67890"])` — batch fetch
- `ym_get_album(album_id=..., include_tracks=true)` — album with tracks
- `ym_artist_tracks(artist_id=..., page=0)` — paginated artist tracks

### Playlist Management

`ym_playlists` is action-dispatched. Identify a playlist by `kind` (numeric YM playlist kind), not by a generic `playlist_id`. Mutating actions need a fresh `revision`.

- `ym_playlists(action="list")` — list user's YM playlists
- `ym_playlists(action="get", kind=1234)` — get playlist metadata
- `ym_playlists(action="get_tracks", kind=1234)` — get playlist tracks (id/title/artists)
- `ym_playlists(action="create", name="My Set")` — create new playlist
- `ym_playlists(action="rename", kind=1234, name="New name")`
- `ym_playlists(action="delete", kind=1234)`
- `ym_playlists(action="add_tracks", kind=1234, track_ids=["t1", "t2"], revision=N)` — bare track IDs; album resolution happens server-side
- `ym_playlists(action="remove_tracks", kind=1234, track_ids=["t1"])` — removes by track_id (not by position)

### Likes
- `ym_likes(action="get_liked")` — get liked track IDs
- `ym_likes(action="add", track_ids=[...])` — like tracks
- `ym_likes(action="remove", track_ids=[...])` — unlike

### Bidirectional Sync
- `sync_playlist(playlist_id=..., direction="pull")` — pull YM → local (default)
- `sync_playlist(playlist_id=..., direction="push")` — push local → YM
- `conflict_strategy="source_wins"` (default) — source of truth wins silently
- `dry_run=true` (default) — preview changes; pass `false` to apply

### Push DJ Set to YM
- `push_set_to_ym(set_id=..., ym_playlist_name="My DJ Set", mode="auto")`
- `mode` ∈ `{create, update, auto}` — `auto` updates an existing YM playlist with the same name, otherwise creates one

## Source of Truth

Each playlist has a `source_of_truth`:
- `"local"` — local DB is authoritative, push changes to YM
- `"yandex"` — YM is authoritative, pull changes to local

Sync direction follows source of truth by default.

## YM API Quirks

See @docs/ym-api-guide.md for full details. Highlights:

- **Rate limiting**: 1.5s between calls + exponential backoff on 429
- **Playlist edits use diff format**: handled inside the client
- **`revision` is required** for `add_tracks` — fetch it via `ym_playlists(action="get", kind=...)` first
- **Broken endpoints**: artist brief-info (403 Antirobot), lyrics (400 HMAC) — skipped

## Tips

- Always `sync_playlist` before building sets from YM-sourced playlists
- Use `dry_run=true` first to see what would change
- Batch operations (get_tracks, get_albums) are more efficient than one-by-one
- Track IDs are strings in YM (not integers)
