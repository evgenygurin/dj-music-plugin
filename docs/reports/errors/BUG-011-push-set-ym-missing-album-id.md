# BUG-011: push_set_to_ym fails with YM API 400 validation error

**Status:** OPEN (2026-03-27)

## Symptom

`push_set_to_ym` fails with `APIError: YM API error 400` validation error when creating a playlist from a set.

## Root Cause

YM playlist add_tracks requires `"trackId:albumId"` format. Tracks imported via `import_tracks` may not have album metadata enriched, so albumId is missing.

## Steps to Reproduce

```text
1. import_tracks(track_refs=["ym:129142659", ...])
2. manage_playlist(action=add_tracks, ...)
3. build_set(playlist_id=6, ...)
4. push_set_to_ym(set_id=19, mode=create) → 400 error
```

## Fix

- Ensure `import_tracks` enriches YM metadata (including albumId) from YM API
- Or: `push_set_to_ym` should fetch albumId for tracks missing it before calling YM API
