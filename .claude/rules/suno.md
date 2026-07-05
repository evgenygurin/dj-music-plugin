# Suno Provider (opt-in)

Generation provider for DJ-utility assets (intro/outro/bridge/rescue loops).
Code under `app/providers/suno/` — `client.py` (httpx wrapper + Clerk bearer),
`adapter.py` (Provider protocol), `session_auth.py` (no-browser credential
loader), `client_errors.py`. Config: `app/config/suno.py` (`DJ_SUNO_*`). Wired
in `app/server/lifespan.py:build_suno_adapter` (registered only when
`SunoSettings.enabled`). Prompt: `suno_set_asset_workflow`.

## Adapter surface (`ProviderRegistry` name `suno`)

- `read(entity, id, params)` — entities: `generation` (poll a clip by id),
  `account` (live balance + capabilities).
- `write(entity="generation", operation, params)`:
  - `create` — params: `prompt` (REQUIRED, non-empty), `title?`, `tags?`
    (list|str), `instrumental?`, `model?`, `negative_tags?`, `lyrics?`,
    `extra?`. Returns `generation_id` (first clip, pollable), `clip_ids`,
    `batch_id`, `status`, `request` echo.
  - `cancel` — params: `generation_id`.
  - `download` — params: `generation_id`, `target_dir?`, `title?`, `filename?`,
    `suffix?` (.mp3), `audio_url?`. Returns `file_path`, `file_size`.
- `search` / catalog is unsupported (raises `ValidationError`).

## Auth (no-browser session)

Suno uses **header-based Clerk with no persisted `__session` cookie**. Modes:

- **session** (default): `DJ_SUNO_COOKIE_HEADER` and/or `DJ_SUNO_BEARER_TOKEN` /
  `DJ_SUNO_CLIENT_TOKEN` + `DJ_SUNO_DEVICE_ID`, or a JSON
  `DJ_SUNO_STORAGE_STATE_PATH`. Client sends `Cookie`, `Origin/Referer`
  (`https://suno.com`), `browser-token`, `device-id`, and
  `Authorization: Bearer <jwt>`.
- **api_key** (`DJ_SUNO_AUTH_MODE=api_key` + `DJ_SUNO_PAYLOAD_MODE=generic`):
  generic bearer/API path for Suno-compatible providers.

**Bearer lifetime ~1 h.** A cookie-only `.env` cannot mint a bearer
server-side (`/v1/client` reports zero sessions for this account), so the live
JWT comes from the browser. Refresh with
`uv run python scripts/suno_refresh_token.py` (needs Chrome open + logged into
suno.com + View ▸ Developer ▸ "Allow JavaScript from Apple Events"). Never
launch Playwright/OAuth from the plugin; never bypass CAPTCHA/2FA — pause and
ask the user to refresh credentials.

## Verified-live contract (2026-07-05) — see [[project_suno_live_api_contract]]

- **create `POST /api/generate/v2-web/`, FLAT payload** (NOT wrapped in
  `params`). `prompt` must be non-empty (empty string reads as `missing`).
- **status `GET /api/feed/v2/?ids={clip_id}`** → `{"clips":[...]}`. Poll **clip
  ids** (`clip_ids`), not the **batch id** create returns
  (`/api/feed/v2/?ids=<batch>` is empty). The old `/api/feed/?ids=` returns [].
- **model `mv`**: free default `chirp-auk-turbo`; `chirp-fenix` (v5.5),
  `chirp-crow` (v5), `chirp-auk`/`bluejay` (v4.5) are PRO → 403 on free; an
  empty `mv` defaults to a paid model → 403. Always send a model.
- **captcha `/api/c/check` is POST** (`ctype` body); GET → 405. The pre-gen
  guard is best-effort — endpoint drift (405/422/404) never blocks a gen.
- **download**: audio is on off-host CDN (`cdn1.suno.ai`); the client strips
  Suno/Clerk auth headers for off-host URLs (`_download_headers`) — no leak.
- **account**: `GET /api/billing/info/` → `total_credits_left`, plan, `models`.

## Gotchas

- `create` returns 2-4 variant clips per batch; `generation_id` = first clip.
- Generated files stay **export-side assets** — do NOT `entity_create(
  entity="audio_file")` for them (needs an existing local track id). See
  [[project_analyze_requires_audio_file]].
- `chirp-fenix` in old configs is a PAID model — set `DJ_SUNO_MODEL` per plan.
- Rate limiting mirrors yandex (`TokenBucketRateLimiter`, no in-`_request`
  retry loop; 429 raises `RateLimitedError`, backoff on next `acquire`).
