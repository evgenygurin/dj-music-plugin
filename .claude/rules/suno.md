# Suno Provider (opt-in)

Generation provider for DJ-utility assets (intro/outro/bridge/rescue loops).
Code under `app/providers/suno/` — `client.py` (httpx wrapper + API/Clerk auth,
generic `api_call` / `upload_file`), `adapter.py` (Provider protocol),
`endpoints.py` (sunoapi.org registry), `endpoints_web.py` (browser-session Suno
web registry), `session_auth.py`
(no-browser credential loader), `client_errors.py`. Config: `app/config/suno.py`
(`DJ_SUNO_*`). Wired in `app/server/lifespan.py:build_suno_adapter` (registered
only when `SunoSettings.enabled`). Prompt: `suno_set_asset_workflow`.

## Two surfaces, one adapter (mode-gated)

The adapter surface is **mode-dependent** (`SunoAdapter.entities_supported` /
`operations_supported` are set from `payload_mode` in `__init__`):

- **session** (browser Suno web, `studio-api-prod.suno.com`) — **project
  default**. Minimal surface: `generation` × `create|cancel|download` +
  `account` read + `generation` read.
- **sunoapi** (`api.sunoapi.org`, `api_key` mode) — **full sunoapi.org REST
  surface** below. Endpoints declared in `endpoints.py` from the sunoapi.org
  OpenAPI specs. These do NOT exist on the browser host — calling a
  sunoapi-only op in session mode raises a typed `ValidationError`
  ("requires api_key/sunoapi mode").

Fields use the documented **camelCase** names; the adapter's `pull_field` also
accepts snake_case (`audio_id`→`audioId`) + explicit aliases
(`callback_url`→`callBackUrl`, `calBackUrl`). `callBackUrl` is injected from
`DJ_SUNO_CALLBACK_URL` (default empty — the DJ flow polls, callbacks optional);
`model` is injected/coerced to each endpoint's allowed enum.

## Adapter surface — session / suno_web mode (`ProviderRegistry` name `suno`)

Full browser-session Suno web surface (`studio-api-prod.suno.com`), declared in
`app/providers/suno/endpoints_web.py`, reverse-engineered from the live suno.com
JS bundle + gcui-art/suno-api and **validated live** (2026-07-06). Available
only in `payload_mode="suno_web"`; a web-only op in sunoapi mode raises a typed
error (and vice versa). Wire keys are snake_case.

**Generation** (`write`, entity `generation`):
- `create` — `prompt` (REQUIRED, non-empty), `title?`, `tags?`, `instrumental?`,
  `model?` (mv, default `chirp-auk-turbo`), `negative_tags?`, `lyrics?`, `extra?`.
  → `generation_id` (first pollable clip), `clip_ids`, `batch_id`, `status`.
- `extend` — `continue_clip_id`+`continue_at` (REQUIRED) + `prompt?`/`tags?`/
  `title?`/`instrumental?`. Posts `/api/generate/v2-web/` with `task:"extend"`.
- `concat` — `clip_id` (merge an extension chain into one full song).
- `cancel`, `download` (as before).

**Editing / creation** (`write`):
- `stem` × `create` (`/api/edit/stems/{clip_id}/`, empty body → `{clips:[…]}`),
  `sample_pack` (`generate_sample_pack`).
- `wav` × `create` (`convert_wav`, 204 accepted → read via clip kind=wav).
- `edit` × `crop` (`crop_start_s`,`crop_end_s`,`title?`), `fade` (`fade_in_time`,
  `fade_out_time`,`title?`), `reverse` (`clip_id`,`title?`) — each returns a
  pollable `action_clip_id`/`id` as `generation_id`.
- `remaster` × `create` (upsample: `clip_id` + optional `model_name`,`tags`,
  `freedom`,`tone`,`strength`,`stereo_width`,`clarity`,`variation_category`).
- `persona` × `create` (`name`,`description`,`root_clip_id?`,…).
- `lyrics` × `create` (`prompt`).
- `playlist` × `create` (`name`), `add_tracks`/`remove_tracks`
  (`playlist_id`,`clip_ids`).

**Reads** (`read`):
- `generation` (poll a clip by id), `account` (balance + `payload_mode`).
- `clip` — `params={"kind": …}` multiplexes: `info`(default,`/api/clip/{id}`),
  `stems`, `wav`, `downbeats`, `sections`, `waveform`, `aligned_lyrics`.
  `downbeats`/`sections`/`waveform` feed the plugin's own beatgrid/section data.
- `lyrics` (by id), `persona` (by id, or list when id omitted), `playlist` (by id).

`search` / catalog is unsupported (raises `ValidationError`).

## Adapter surface — sunoapi.org mode (adds, on top of the above)

Task creates return `{task_id, status, ready, audio_url, raw}` (poll the task
via `read`). All `write` unless noted.

- `generation` × `extend | upload_cover | upload_extend | add_instrumental |
  add_vocals | mashup | replace_section | sounds` — the documented generate
  variants (`/api/v1/generate/*`). Poll via `read(entity="generation", id=taskId)`.
- `lyrics` × `create` (`/api/v1/lyrics`) + `timestamped`
  (`/api/v1/generate/get-timestamped-lyrics`); `read` → `/api/v1/lyrics/record-info`.
- `wav` × `create` (`/api/v1/wav/generate`); `read` → `/api/v1/wav/record-info`.
- `vocal_removal` (stem separation) × `create` (`type=separate_vocal|split_stem`);
  `read` → `/api/v1/vocal-removal/record-info`.
- `midi` × `create`; `read` → `/api/v1/midi/record-info`.
- `video` (mp4) × `create`; `read` → `/api/v1/mp4/record-info`.
- `cover` (album art) × `create` (`/api/v1/suno/cover/generate`); `read` →
  `/api/v1/suno/cover/record-info`.
- `persona` × `create` (`/api/v1/generate/generate-persona`, sync).
- `style` × `boost` (`/api/v1/style/generate`, sync, `content` only).
- `voice` (custom voice) × `validate | generate | regenerate | check`;
  `read(entity="voice", id, params={"kind":"validate"|"record"})` →
  `/api/v1/voice/validate-info` or `/api/v1/voice/record-info`.
- `file` × `upload_base64 | upload_url | upload_stream` — targets the separate
  file-upload host (`DJ_SUNO_UPLOAD_BASE_URL`, default
  `https://sunoapiorg.redpandaai.co`). `upload_stream` reads `local_path` and
  posts multipart. Returns `{upload_url, raw}`.

## Auth modes

- **session / Suno web** (project default): `DJ_SUNO_COOKIE_HEADER` and/or
  `DJ_SUNO_BEARER_TOKEN` /
  `DJ_SUNO_CLIENT_TOKEN` + `DJ_SUNO_DEVICE_ID`, or a JSON
  `DJ_SUNO_STORAGE_STATE_PATH`. Client sends `Cookie`, `Origin/Referer`
  (`https://suno.com`), `browser-token`, `device-id`, and
  `Authorization: Bearer <jwt>`. Payload mode defaults to `suno_web`.
- **api_key / SunoAPI** (opt-in only when a key exists): set
  `DJ_SUNO_AUTH_MODE=api_key` + `DJ_SUNO_API_KEY`. `DJ_SUNO_BASE_URL` is
  optional and defaults to `https://api.sunoapi.org`. Payload mode defaults to
  `sunoapi`; generation uses `POST /api/v1/generate`, status uses
  `GET /api/v1/generate/record-info?taskId=...`, and credits use
  `GET /api/v1/generate/credit`.
- **generic**: `DJ_SUNO_PAYLOAD_MODE=generic` remains available only for
  non-SunoAPI-compatible providers with custom endpoint shapes.

For session mode, bearer lifetime is ~1 h. A cookie-only `.env` cannot mint a bearer
server-side (`/v1/client` reports zero sessions for this account), so the live
JWT comes from the browser. Refresh with
`uv run python scripts/suno_refresh_token.py` (needs Chrome open + logged into
suno.com + View ▸ Developer ▸ "Allow JavaScript from Apple Events"). Never
launch Playwright/OAuth from the plugin; never bypass CAPTCHA/2FA — pause and
ask the user to refresh credentials.

## SunoAPI contract (`docs.sunoapi.org`, 2026-07-05)

- **auth**: `Authorization: Bearer <DJ_SUNO_API_KEY>`.
- **create**: `POST /api/v1/generate`. Required fields:
  `customMode`, `instrumental`, `callBackUrl`, `model`. In custom mode, send
  `style` and `title`; send `prompt` when vocals/lyrics are requested.
- **status**: `GET /api/v1/generate/record-info?taskId={taskId}`. Response
  status values include `PENDING`, `TEXT_SUCCESS`, `FIRST_SUCCESS`, `SUCCESS`,
  and documented failure states. Audio variants live under
  `response.sunoData[]` with `id`, `audioUrl`, `streamAudioUrl`, `title`,
  `tags`, and `duration`.
- **credits**: `GET /api/v1/generate/credit` returns the remaining credit count
  as `data`.
- **cancel**: not present in the public SunoAPI OpenAPI spec. The adapter keeps
  `operation="cancel"` for legacy web/generic providers only; API-key mode has
  no cancel endpoint unless `DJ_SUNO_CANCEL_PATH` is explicitly configured.
- **models**: `V4`, `V4_5`, `V4_5PLUS`, `V4_5ALL`, `V5`, `V5_5`. If a legacy
  `chirp-*` model leaks into `sunoapi` mode, the adapter falls back to `V4_5`.

## Suno web session contract (2026-07-05) — see [[project_suno_live_api_contract]]

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
