---
description: Yandex Music client patterns
globs:
  - app/ym/**/*.py
  - app/controllers/tools/yandex/**/*.py
---

# Yandex Music Client

- All methods async
- Use `httpx.AsyncClient` with base_url from `settings.ym_base_url`
- Rate limiting: `settings.ym_rate_limit_delay` between calls + exponential backoff on 429
- Return typed Pydantic models, not raw dicts
- Handle HTTP errors specifically:
  - 429 → RateLimitedError (retry with backoff)
  - 401/403 → AuthFailedError
  - 400 → APIError with response body
- Playlist modifications use JSON diff array format (YM-specific)
- After playlist modification, always re-fetch for fresh revision/indices
- Known broken endpoints: artist brief-info (403), lyrics (400 HMAC) — skip gracefully
- OAuth token from `settings.ym_token`, user ID from `settings.ym_user_id`

## Gotchas

- Search API: `type=tracks` (plural), not `type=track`
- Playlist add_tracks: albumId resolves automatically via `ym.resolve_track_ids_with_albums()` — pass bare track IDs, `"trackId:albumId"` formatting happens under the hood
- `ym_playlists` supports `action=get_tracks` (returns tracks with id/title/artists) and working `action=remove_tracks` (removes by track_id, not by index)
