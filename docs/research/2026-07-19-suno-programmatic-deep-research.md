# Suno Programmatic Deep Research

Date: 2026-07-19

## Executive Summary

This project should treat Suno as two different programmatic surfaces behind one provider name:

- **Browser-session Suno web** is the project default. It uses user-supplied Suno/Clerk browser credentials, works without browser automation, and is good for normal generation plus web-only refinement operations already implemented in `app/providers/suno/endpoints_web.py`.
- **SunoAPI gateway** is opt-in via `DJ_SUNO_AUTH_MODE=api_key` and `DJ_SUNO_API_KEY`. It has the broader documented REST surface: generation, uploads, cover/extend, add vocals/instrumental, stems, WAV, MIDI, MP4, cover art, Persona, style boost, and Suno Voice.

The safest agent behavior is: preflight account/mode first, select only operations supported by that mode, always poll the right id type, never automate browser login or CAPTCHA, and keep generated audio as export-side assets until local-file track import exists.

## Sources

- Suno help categories: `https://help.suno.com/en/categories/550017-making-music`, `https://help.suno.com/en/categories/550145-rights-ownership`, `https://help.suno.com/en/categories/1708865-studio`.
- Suno terms: `https://suno.com/terms`, last revision shown as 2026-03-26.
- SunoAPI docs index: `https://docs.sunoapi.org/llms.txt`.
- SunoAPI pages fetched: `generate-music.md`, `get-music-generation-details.md`, `get-remaining-credits.md`, `suno-voice-generate.md`, `separate-vocals-from-music.md`, `upload-and-extend-audio.md`.
- Reverse-engineering/community reference: `https://github.com/gcui-art/suno-api`.
- FastMCP docs via Context7 `/prefecthq/fastmcp`: prompts/resources use decorators and `PromptResult`.
- Project contract: `.claude/rules/suno.md` and `app/providers/suno/endpoints.py` / `endpoints_web.py`.

## Current Model Lineup

### SunoAPI Gateway Models

SunoAPI documents these generation model enums:

- `V4`: refined song structure and audio quality, documented as up to 4 minutes.
- `V4_5`: smarter prompts, genre blending, faster output, documented as up to 8 minutes.
- `V4_5PLUS`: richer sound and more creative range, documented as up to 8 minutes.
- `V4_5ALL`: better song structure, documented as up to 8 minutes; upload-extend docs note a stricter 1-minute uploaded-audio limit for this model.
- `V5`: current higher-quality model with faster/superior musical expression.
- `V5_5`: current voice/custom-model oriented model; SunoAPI notes `voice_persona` usage only with `V5` and `V5_5`.

For API-key mode, default to `V5_5` when the task needs custom voice / `voice_persona`, otherwise default to `V5` or `V4_5ALL` based on account availability and desired structure. Keep `V4_5` as the conservative compatibility fallback.

### Browser-Session Web Model Keys

The project contract records current web/session keys as version-dependent:

- `chirp-auk-turbo`: project free-safe default for web session mode.
- `chirp-fenix`: mapped in project notes to v5.5-like paid behavior.
- `chirp-crow`: mapped in project notes to v5-like paid behavior.
- `chirp-auk` / `bluejay`: mapped in project notes to v4.5-like paid behavior.

Agents must read account/model access first. Paid web model keys can return 403 on free accounts; an empty `mv` can default to a paid model and fail.

## Two API Surfaces

### Browser-Session Suno Web

Host: `https://studio-api-prod.suno.com`, with Clerk auth material from `https://auth.suno.com`.

Auth material is supplied by the user’s already logged-in browser session: `DJ_SUNO_COOKIE_HEADER`, `DJ_SUNO_BEARER_TOKEN` / `DJ_SUNO_CLIENT_TOKEN`, `DJ_SUNO_DEVICE_ID`, or `DJ_SUNO_STORAGE_STATE_PATH`. The plugin must not launch Playwright/OAuth or bypass CAPTCHA/2FA. If credentials expire, refresh with `uv run python scripts/suno_refresh_token.py` after the user is logged into Suno in their own browser.

Important session contract details from the project’s live-validated notes:

- Create uses `POST /api/generate/v2-web/`.
- Payload is flat, not wrapped in `params`.
- `prompt` is required and must be non-empty.
- Poll with `GET /api/feed/v2/?ids={clip_id}`.
- Poll clip ids from `clip_ids`, not the batch id.
- Download URLs can be off-host CDN URLs such as `cdn1.suno.ai`; do not send Suno/Clerk auth headers to off-host downloads.
- Account read uses `GET /api/billing/info/` and returns credits/plan/models.

Implemented web-mode write surface includes generation create/extend/concat/cancel/download, stems, WAV conversion, crop/fade/reverse edits, remaster, persona, lyrics, and playlist operations. Implemented read surface includes generation/account plus clip multiplex reads for info, stems, WAV, downbeats, sections, waveform, and aligned lyrics.

The web audio upload flow is intentionally not implemented as a full automation path because the final initialize-clip step is bot-walled. Use SunoAPI upload workflows when external audio is needed.

### SunoAPI Gateway

Host: `https://api.sunoapi.org`. Auth is `Authorization: Bearer <DJ_SUNO_API_KEY>`.

Main generation endpoint:

- `POST /api/v1/generate`.
- Required fields: `customMode`, `instrumental`, `callBackUrl`, `model`.
- In custom vocal mode, `style`, `prompt`, and `title` are required.
- In custom instrumental mode, `style` and `title` are required.
- In non-custom mode, only `prompt` is required by behavior, but the wire schema still requires the shared fields.
- Each request returns exactly 2 songs.
- Stream URL is documented as available in 30-40 seconds; downloadable song URL in 2-3 minutes.
- Concurrency limit is documented as 20 requests every 10 seconds.

Polling endpoint:

- `GET /api/v1/generate/record-info?taskId={taskId}`.
- Status values include `PENDING`, `TEXT_SUCCESS`, `FIRST_SUCCESS`, `SUCCESS`, `CREATE_TASK_FAILED`, `GENERATE_AUDIO_FAILED`, `CALLBACK_EXCEPTION`, and `SENSITIVE_WORD_ERROR`.
- Audio variants live under `response.sunoData[]` with ids, audio URLs, stream URLs, title, tags, model name, and duration.

Credits endpoint:

- `GET /api/v1/generate/credit` returns integer credits as `data`.
- Insufficient credits are documented as error code 429.

Additional SunoAPI surface documented by `llms.txt` and already modeled in `endpoints.py` includes extend, upload-cover, upload-extend, add vocals, add instrumental, mashup, replace section, lyrics and timestamped lyrics, WAV, vocal removal / stem split, MIDI, MP4 video, cover art, Persona, style boost, Suno Voice validate/generate/regenerate/check, and file upload by base64/URL/stream.

## Prompt Engineering For Programmatic Suno

### Field Split

Use fields according to mode:

- **Custom vocal generation:** `prompt` is exact lyrics; `style` holds genre, instrumentation, voice, arrangement, mix notes, BPM/key, and quality constraints; `title` is required.
- **Custom instrumental generation:** `prompt` can be omitted or minimal; `style` must carry the complete musical brief; `instrumental=true`.
- **Non-custom/simple generation:** `prompt` is a short natural-language idea; generated lyrics may not match the prompt exactly.
- **Negative tags:** use `negativeTags` / `negative_tags` for explicit exclusions such as `female lead`, `choir`, `long intro`, `heavy metal`, or `bright EDM diva`, depending on target.

### Structure And Vocal Control

Use readable song section tags in lyrics:

- `[Intro]`, `[Verse]`, `[Pre-Chorus]`, `[Hook]`, `[Chorus]`, `[Bridge]`, `[Build]`, `[Drop]`, `[Breakdown]`, `[Outro]`.
- Performance cues can be bracketed (`[deadpan, low, close mic]`) or parenthetical for ad-libs (`(эй)`, `(ха)`, `(скр)`).
- Keep cues short. Over-specified prompts can reduce musicality.

### Sliders And Weights

SunoAPI exposes numeric controls:

- `styleWeight`: how strongly to follow style guidance, 0.00-1.00.
- `weirdnessConstraint`: creative deviation/novelty constraint, 0.00-1.00.
- `audioWeight`: influence of input audio where upload/cover/extend applies, 0.00-1.00.

For controlled DJ utility assets, use moderate style weight and low-to-moderate weirdness. For exploration, increase weirdness but keep BPM/key/bar constraints explicit.

### Voice Locking

Prefer prompt-only voice blocks for project characters unless the user explicitly asks for Persona or Suno Voice creation. Existing project recipes include RimJoba, Swallow Boy, and Taras. For formal Suno Voice through SunoAPI:

- Generate a validation phrase.
- Record the exact phrase in a singing voice; SunoAPI explicitly recommends singing over plain speech.
- Upload/host the verification audio and submit `verifyUrl`.
- Poll voice record info for `voiceId`.
- Use `personaId=<voiceId>` and `personaModel="voice_persona"` with V5/V5_5 generation.

Suno terms state a user may only create a voice model resembling their own voice. Do not attempt to create another person’s voice model.

### Techno / DJ Utility Assets

For DJ assets, favor:

- Instrumental mode.
- Explicit BPM, key/Camelot intent, bar count, and energy role.
- `no lead hook`, `no vocal`, `no long intro`, `loopable`, `DJ tool`, `clean 8/16/32-bar phrasing`.
- Conservative arrangement: intro beds, outro tails, bridge loops, rescue loops, texture beds, and gap fills.

Good style sketch:

`hypnotic dub techno DJ tool, 126 BPM, Camelot 8A, 16-bar loop, deep rolling kick, muted dub chord stabs, tape echo, no vocal, no lead melody, clean intro/outro handles, mixable low-end`

## Operational Limits And Rights

- SunoAPI generation: 20 requests every 10 seconds; each request returns exactly 2 songs.
- SunoAPI generated files are documented as retained for 15 days for generation and 14 days for some processing/upload outputs.
- Prompt/style/title limits depend on model: V4 has shorter limits; V4.5/V5 families support longer prompt/style/title fields per docs.
- Stem separation costs credits. SunoAPI documents `separate_vocal` as 10 credits, `split_stem` as 50 credits, and `split_stem_advanced` as 20 credits at the fetched page; always re-check billing before repeated calls.
- Free-plan Suno songs are intended for personal non-commercial use.
- Songs made while subscribed to Pro/Premier are granted commercial use rights, subject to Suno terms and rights complexity.
- Paid subscription does not automatically grant retroactive commercial rights to songs made on the free plan.
- Suno terms prohibit scraping/circumvention and creating voice models of other people.

## Automation Gotchas

- Do not automate login, OAuth, CAPTCHA, 2FA, or bot-detection bypass.
- Browser-session bearer lifetime is short; refresh from the user’s browser session.
- Cookie-only auth cannot be assumed to mint a bearer server-side.
- Web `create` needs a non-empty prompt and explicit model.
- Paid web model keys can 403 on free accounts.
- Session mode polls clip ids, not batch ids.
- SunoAPI mode polls task ids.
- Callbacks are optional for this plugin because polling is the practical MCP path; still send empty or configured `callBackUrl` as required by gateway schema.
- Web upload initialize is bot-walled; use SunoAPI upload-cover/upload-extend for external audio.
- Re-running stems or advanced processing can charge again and may not be cached.
- Download off-host CDN URLs without Suno auth headers.

## FastMCP Fit

FastMCP v3 supports prompt/resource decorators and `PromptResult`. This project’s filesystem discovery and tests already expect pure prompt modules and static reference resources. The correct integration path is therefore new prompt/resource files plus tests, not new provider orchestration code.
