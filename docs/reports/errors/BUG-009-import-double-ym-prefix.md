# BUG-009: import_tracks creates double "ym:" prefix in title

**Status:** OPEN (2026-03-27)

## Symptom

When importing tracks with `track_refs=["ym:129142659"]`, the created track gets title `YM:ym:129142659` instead of `YM:129142659`.

## Expected

Title should be `YM:129142659` (or the actual track title from YM API enrichment).

## Steps to Reproduce

```text
import_tracks(track_refs=["ym:129142659"])
list_tracks → title = "YM:ym:129142659"
```

## Root Cause

The `ym:` prefix from the track_ref string is not stripped before being used as the fallback title. The import code likely prepends "YM:" to the raw ref including the already-present "ym:" prefix.

## Impact

- Track titles contain ugly double prefix
- Searching by title may fail
- YM metadata enrichment may not trigger (title mismatch)
