# Yandex Music API Guide

Async HTTP client wrapping YM REST API. Key quirks and patterns.

## Client Architecture

```text
YandexMusicClient
├── _request()           # base: auth header, rate limit, retry
├── search()             # tracks, albums, artists, playlists
├── get_tracks()         # batch by IDs
├── get_album()          # with/without tracks
├── get_artist_tracks()  # paginated
├── get_similar()        # similar tracks
├── get_playlist()       # by owner_id:kind
├── create_playlist()
├── modify_playlist()    # add/remove tracks (diff format!)
├── get_liked_ids()      # liked track IDs
├── download_track()     # resolve URL → download MP3
└── ...

RateLimiter
├── Token bucket: 1 request per 1.5s (configurable)
├── Exponential backoff on 429: 2x multiplier, max 3 retries
└── Backoff resets after successful request
```

## Authentication

```text
Authorization: OAuth {settings.ym_token}
```

Token obtained from Yandex OAuth. No refresh mechanism in API — token is long-lived.

## Rate Limiting

YM API rate-limits aggressively (HTTP 429 on both reads and writes):

```python
# In RateLimiter:
# 1. Wait settings.ym_rate_limit_delay between requests
# 2. On 429: wait retry_after header or 2^attempt * base_delay
# 3. Max settings.ym_retry_attempts retries
# 4. After max retries: raise RateLimitedError
```

## Known API Quirks

### Playlist Modifications Use JSON Diff Format

YM expects playlist changes as a diff array, NOT a simple track list:

```json
// Adding tracks: POST /users/{uid}/playlists/{kind}/change-relative
{
  "diff": [
    {"op": "insert", "at": 0, "tracks": [
      {"id": "12345", "albumId": "6789"}
    ]}
  ]
}
```

### Delete Uses Inclusive/Exclusive Index Ranges

```json
// Removing track at position 3:
{"diff": [{"op": "delete", "from": 3, "to": 4}]}
// from=inclusive, to=exclusive
```

### After Every Modification, Re-Fetch

Playlist `revision` changes on every edit. Always re-fetch after modify:

```python
await client.modify_playlist(playlist_id, diff)
updated = await client.get_playlist(playlist_id)  # fresh revision
```

### Broken Endpoints

| Endpoint | Error | Workaround |
|----------|-------|------------|
| Artist brief-info | 403 Antirobot | Use artist tracks/albums instead |
| Lyrics | 400 requires HMAC | Skip lyrics feature |

### Download URL Resolution

Two-step process:
1. `GET /tracks/{id}/download-info` → list of download options
2. Pick highest bitrate → construct download URL with timestamp + sign
3. `GET {download_url}` → MP3 file

### Batch Operations

Many endpoints accept batch IDs:
- `GET /tracks?trackIds=1,2,3` — up to 100 per request
- `POST /playlists/list` with body `{"playlistIds": [...]}` — batch playlists
- `POST /albums` with body `{"albumIds": [...]}` — batch albums

### Search Response Structure

```json
{
  "result": {
    "tracks": {"results": [...], "total": N},
    "albums": {"results": [...], "total": N},
    "artists": {"results": [...], "total": N},
    "playlists": {"results": [...], "total": N}
  }
}
```

When `type` specified, only that section populated.

## Error Handling

| HTTP Status | Error Type | Action |
|-------------|-----------|--------|
| 200 | — | Parse response |
| 400 | `APIError` | Log body, raise |
| 401 | `AuthFailedError` | "Check DJ_YM_TOKEN" |
| 403 | `AuthFailedError` or `APIError` | May be Antirobot |
| 429 | `RateLimitedError` | Retry with backoff |
| 500+ | `APIError` | Retry up to max_attempts |

## Data Model Mapping

YM responses → local models:

| YM Field | Local Field | Notes |
|----------|-------------|-------|
| `id` | `yandex_track_id` | String in YM, stored as string |
| `albums[0]` | `YandexMetadata.album_*` | Track can have multiple albums |
| `durationMs` | `Track.duration_ms` | Direct mapping |
| `coverUri` | `YandexMetadata.cover_uri` | Template: replace `%%` with size |
| `explicit` | `YandexMetadata.explicit` | Boolean |
