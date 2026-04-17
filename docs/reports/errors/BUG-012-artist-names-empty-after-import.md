# BUG-012: artist_names empty after import from YM

**Date**: 2026-03-27
**Severity**: Medium
**Status**: OPEN

## Observed

After importing 30 tracks via `import_tracks` with YM track refs, all tracks show `artist_names: []` in `get_playlist(include_tracks=true)`.

## Expected

`artist_names` should be populated from YM metadata during import (artist data is present in YM search results).

## Related

- BUG-006: Artist-track association not created during import (OPEN in CLAUDE.md)
- `import_tracks` enriches YM metadata (`enriched: 30`) but artist associations are not created

## Reproduction

```text
1. ym_search(query="techno", type="tracks")
2. import_tracks(track_refs=[...], playlist_id=1)
3. get_playlist(id=1, include_tracks=true)
   -> all artist_names: []
```

## Impact

Track listings show titles without artist info, making it harder to identify tracks.
