---
description: Yandex Music client patterns
globs:
  - app/providers/yandex/**/*.py
---

# Yandex Music Client (v1)

- Code lives under `app/providers/yandex/` —
  `client.py` (raw httpx wrapper), `adapter.py` (Provider protocol
  adapter), `rate_limiter.py` (token bucket), `filters.py` (genre /
  duration / title rules).
- All methods async. `YandexClient` returns raw dicts straight from YM;
  `YandexAdapter` maps to v1 shapes; handlers (`track_import`) bridge to
  DB models.
- `YandexClient(token, user_id, base_url=..., rate_limiter=..., timeout_s=30.0)`.
  Default `base_url="https://api.music.yandex.net"`.
- Rate limiting via `TokenBucketRateLimiter(delay_s=1.5,
  base_backoff_s=2.0, max_retries=3)` — exponential backoff on 429
  (`base_backoff_s * 2 ** (retry - 1)`), resets on success.
- HTTP error mapping (`client.py::_request`):
  - 401 / 403 → `AuthFailedError("auth failed ... check DJ_YM_TOKEN")`
  - 429 → `RateLimitedError` (increments retry count; once
    `retries_exhausted` → raise)
  - 4xx+ → `APIError(f"{code}: {body[:500]}")`
- Playlist modifications use JSON diff array format (YM-specific).
  Adapter fetches current revision via `_resolve_revision` when caller
  doesn't supply one.
- Known-broken endpoints (skip gracefully, not exposed by adapter):
  artist brief-info (403 Antirobot), lyrics (400, requires HMAC).
- OAuth token from `settings.yandex.token`; user id from
  `settings.yandex.user_id` (split config under `app/config/yandex.py`).

## Adapter surface

`YandexAdapter` implements the universal `Provider` protocol
(`app/registry/provider.py`):

- `read(entity, id, params)` — entities: `track`, `track_batch`,
  `track_similar`, `album`, `artist_tracks`, `playlist`,
  `playlist_list`, `likes`, `dislikes`.
- `write(entity, operation, params)` — operation matrix is declared on
  `YandexAdapter.operations_supported` (ClassVar, source of truth that
  mirrors the `_write_playlist` / `_write_likes` `match` arms; any other
  operation raises `ValueError("unknown <entity> operation: ...")`):
  - `entity="playlist"` × `create | rename | set_description | delete
    | add_tracks | remove_tracks` — there is **no** `create_from_set`;
    push a set as `create` then `add_tracks`.
  - `entity="likes"` × `add | remove`
- `search(query, type, limit)` — plural aliases accepted; client
  rewrites to singular via `_SEARCH_TYPE_ALIASES`.
- `download_audio(track_id, dest?)` — returns local `Path`. URL
  resolution: `/tracks/{id}/download-info` → XML manifest with
  (host, path, s, ts) → `md5(SALT + path[1:] + s)` signed URL.

## Gotchas

- Search at the client layer expects SINGULAR `type=track`; plural
  (`tracks`) works at adapter/tool layer and is rewritten under the
  hood.
- `add_tracks` diff uses BARE track IDs:
  `[{"op":"insert", "at":N, "tracks":[{"id": tid}, ...]}]`. There is
  no automatic `albumId` resolution in v1 — do NOT pass
  `"trackId:albumId"`.
- `remove_tracks` uses `{"op":"delete", "from":N, "to":M}` — index
  range, inclusive / exclusive (YM semantics).
- Playlist id: accepts both `"owner:kind"` and bare `kind`
  (owner defaults to `settings.yandex.user_id`). See
  `YandexClient._split_playlist_id`.
- `provider_write(entity="playlist", operation="set_description")` is
  supported end-to-end (adapter → `client.set_playlist_description`).
- Download salt / MD5 signing lives only in
  `YandexClient._build_signed_mp3_url` — don't duplicate.
- Legacy `ym_*` tools no longer exist; v1 surface is `provider_read` /
  `provider_write` / `provider_search`.
- **`track_batch` legacy `ids` alias (v1.3.7).**
  `YandexAdapter.read("track_batch", params={...})` accepts both
  canonical `track_ids` and legacy `ids` — old call sites that pass
  `{"ids": [...]}` keep working without migration. Numeric IDs are
  auto-stringified by the adapter before hitting the YM client (which
  needs string IDs in the `trackIds=` query param).
- **`provider_read.id` accepts `int | str` (v1.3.7).** YM track IDs
  are naturally numeric, and the previous Pydantic-strict signature
  rejected `id=137518650`. Now both `id=137518650` and `id="137518650"`
  resolve correctly through the dispatcher.
