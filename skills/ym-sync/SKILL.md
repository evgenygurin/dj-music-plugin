---
name: ym-sync
description: "This skill should be used when the user asks to sync a playlist, push or pull from Yandex Music, search YM, manage YM playlists, or manage YM likes. Covers bidirectional sync, playlist management, search and likes."
version: 1.0.1
---

# Yandex Music Sync Workflow

Guide the user through syncing local playlists with Yandex Music via the v1 polymorphic dispatchers. See @docs/tool-catalog.md (**20 tools** = 14 core dispatchers + 6 UI Prefab + 27 resources).

## Namespace Visibility

**Current state (v1.3.7):** `DISABLED_NAMESPACE_TAGS` in `app/server/visibility.py` is an empty frozenset — **every namespace is visible at startup**, including `provider:write` and `sync`. Rationale: Claude Code does not always honour `notifications/tools/list_changed` mid-session, so server-side `mcp.disable(tags=...)` would hide tools without the client knowing they became unlockable.

`unlock_namespace` is still useful for:
- Audit-log workflows (records which namespaces were activated when)
- Clients that DO honour `notifications/tools/list_changed`

```text
unlock_namespace(namespace="provider:write", action="status")   # check status
unlock_namespace(namespace="provider:write", action="unlock")   # unlock (no-op for visibility in Claude Code today)
unlock_namespace(namespace="sync",          action="unlock")
unlock_namespace(namespace="all",           action="unlock")   # provider:write + sync + crud:destructive + ui:read
```

`namespace` accepts: `crud:destructive`, `provider:write`, `sync`, `ui:read`, `all`.

## Sync Actions

### Search YM
- `provider_search(provider="yandex", query="...", type="tracks", limit=20)` — search tracks (plural `tracks`, см. @.claude/rules/ym.md)
- `type` values: `tracks`, `albums`, `artists`, `playlists`, `all`

### Read YM Data (`provider_read`)
- Single track: `provider_read(provider="yandex", entity="track", id=<ym_track_id>)`
- Batch tracks: `provider_read(provider="yandex", entity="track_batch", params={"track_ids": ["t1","t2"]})` (legacy `ids` key still accepted)
- Album: `provider_read(provider="yandex", entity="album", id=<album_id>, params={"include_tracks": true})`
- Artist tracks (paginated): `provider_read(provider="yandex", entity="artist_tracks", id=<artist_id>, params={"page": 0})`
- Similar tracks: `provider_read(provider="yandex", entity="track_similar", id=<ym_track_id>, params={"limit": 20})`
- Playlist: `provider_read(provider="yandex", entity="playlist", id="<owner>:<kind>")` (or pass `params={"kind": 1234}`)
- User playlists: `provider_read(provider="yandex", entity="playlist_list")`
- Liked / disliked: `provider_read(provider="yandex", entity="likes")` / `entity="dislikes"`

### Mutate YM (`provider_write` — namespace `provider:write`, locked)

Identify a playlist by `kind` (numeric). Mutating actions need a fresh `revision` — re-fetch via `provider_read` after each edit.

- Create: `provider_write(provider="yandex", entity="playlist", operation="create", params={"name": "My Set"})`
- Rename: `provider_write(provider="yandex", entity="playlist", operation="rename", params={"kind": 1234, "name": "New"})`
- Delete: `provider_write(provider="yandex", entity="playlist", operation="delete", params={"kind": 1234})`
- Add tracks (bare track IDs, album resolution happens server-side):
  `provider_write(provider="yandex", entity="playlist", operation="add_tracks", params={"kind": 1234, "track_ids": ["t1","t2"], "revision": <rev>})`
- Remove tracks (by track_id, not position):
  `provider_write(provider="yandex", entity="playlist", operation="remove_tracks", params={"kind": 1234, "track_ids": ["t1"], "revision": <rev>})`
- Set description: `provider_write(provider="yandex", entity="playlist", operation="set_description", params={"kind": 1234, "description": "..."})`
- Likes: `provider_write(provider="yandex", entity="likes", operation="add"|"remove", params={"track_ids": [...]})`

### Bidirectional Sync (`playlist_sync` — namespace `sync`, locked)

- Diff preview: `playlist_sync(playlist_id=<local_id>, direction="diff", source="yandex", dry_run=true)`
- Pull (YM → local): `playlist_sync(playlist_id=<local_id>, direction="pull", source="yandex")`
- Push (local → YM): `playlist_sync(playlist_id=<local_id>, direction="push", source="yandex")`
- `dry_run=true` (default) — preview; pass `false` to apply

### Push a DJ Set to YM

No dedicated tool — compose from primitives:
1. Create target YM playlist: `provider_write(... operation="create" ...)`
2. Record the YM `owner:kind` pair on the local playlist (`dj_playlists.platform_ids`) — this is the link the sync tool reads.
3. Sync tracks: `playlist_sync(playlist_id=<local_playlist_id>, direction="push", dry_run=false)`

Or use the `deliver_set_workflow` prompt with `sync_to_ym=true`.

## Source of Truth

Each `playlist` has a `source_of_truth` field — `"local"` or `"yandex"`. Sync direction follows source of truth by default; override explicitly via `direction`.

## YM API Quirks

See @docs/ym-api-guide.md. Highlights:
- **Rate limiting**: 1.5s between calls + exponential backoff on 429
- **Playlist edits use diff format** — handled inside the YandexAdapter
- **`revision` is required** for `add_tracks` / `remove_tracks` — fetch via `provider_read` after each mutation
- **Broken endpoints**: artist brief-info (403 Antirobot), lyrics (400 HMAC) — skipped gracefully

## Tips

- Always `playlist_sync(direction="pull")` before building sets from YM-sourced playlists
- `dry_run=true` on sync previews the diff without mutating
- Batch reads (`track_batch`, `playlist_list`) are cheaper than loop-calling per-ID
- YM track IDs are strings, not integers
