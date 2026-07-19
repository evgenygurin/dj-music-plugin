---
name: suno
description: "Use when generating music with Suno, creating Suno DJ assets, building lyrics/style prompts, voice-locking, extending/concatenating clips, extracting stems/WAV, or debugging Suno auth/model/polling issues. Covers session web mode and sunoapi.org api_key mode."
version: 1.0.0
---

# Suno Production Workflow

Операционный путь для Suno в этом проекте: no-browser session auth по умолчанию, SunoAPI api_key только opt-in. Цель — получить готовые export-side audio assets, не ломая auth, права и mode-gating.

## Steps

1. **Preflight before every generation**
   - `provider_read(provider="suno", entity="account")` — зафиксируй `payload_mode`, credits, plan/models, ошибки auth.
   - `payload_mode=session|suno_web`: текущий **free**-дефолт — `v4.5-all` (сменил free-модель 21.10.2025); `chirp-auk-turbo` — v4.5-turbo вариант. Codenames: `chirp-fenix`=v5.5 (stable, 2026-03-26), `chirp-crow`=v5, `chirp-bluejay`=v4.5+, `chirp-auk`=v4.5 — все PRO, доступны только если account (`usable_models`) их показывает; пустой `mv` → 403.
   - `payload_mode=sunoapi`: модели `V4`, `V4_5`, `V4_5PLUS`, `V4_5ALL`, `V5`, `V5_5`; для `voice_persona` предпочитай `V5_5`/`V5`.
   - Если session истёк: `uv run python scripts/suno_refresh_token.py` после того, как пользователь залогинен в Suno в своём браузере. Не запускай OAuth/Playwright/CAPTCHA из плагина.

2. **Choose the right surface**
   - Web session: normal generate, extend/concat, stems, WAV, crop/fade/reverse, remaster, persona, lyrics, playlist, clip reads.
   - SunoAPI: upload/cover/extend, add vocals/instrumental, mashup, replace section, lyrics/timestamped, WAV, vocal removal/stems, MIDI, MP4, cover art, Persona, style boost, Suno Voice, file upload.
   - Web audio upload initialize is bot-walled; for external audio use SunoAPI upload flows.

3. **Craft the prompt with field discipline**
   - Vocal custom mode: lyrics in `prompt`; genre/voice/arrangement/BPM/key/mix in style/tags; exclusions in negative tags.
   - Instrumental DJ asset: `instrumental=true`, explicit BPM/key/Camelot, bar count, loopable phrasing, no vocal, no lead hook, clean intro/outro handles.
   - Use `reference://suno/prompt-craft` for tags/sliders and `reference://suno/voices` for RimJoba / Swallow Boy / Taras recipes.

4. **Create exactly one generation first**
   - `provider_write(provider="suno", entity="generation", operation="create", params={...})`.
   - Web mode requires a non-empty `prompt` and explicit model; create returns `generation_id`, `clip_ids`, `batch_id`.
   - SunoAPI mode requires gateway fields (`customMode`, `instrumental`, `callBackUrl`, `model`; plus `style`/`title` and lyrics `prompt` when needed) and returns a task id.

5. **Poll the correct id**
   - Web mode: `provider_read(provider="suno", entity="generation", id="<clip_id>")`; poll clip ids, not batch id.
   - SunoAPI mode: poll the task id until `SUCCESS` and `response.sunoData[]` has audio URLs.
   - On failure, report status/raw error; simplify the brief before retrying. Do not spam expensive retries.

6. **Refine only after a ready clip exists**
   - Web: `generation.extend` → `generation.concat`; `stem.create`; `wav.create`; `edit.crop`; `edit.fade`; `edit.reverse`; `remaster.create`.
   - SunoAPI: `generation.upload_cover|upload_extend|add_vocals|add_instrumental|replace_section`; `vocal_removal.create`; `wav.create`; `midi.create`; `video.create`; `cover.create`; `style.boost`; `voice.validate|generate|check`.
   - Stem separation and WAV/advanced processing can cost credits; avoid repeating the same operation blindly.

7. **Download and document assets**
   - `provider_write(provider="suno", entity="generation", operation="download", params={"generation_id":"<ready id>", "target_dir":"suno_out/...", "title":"..."})`.
   - Keep files as export-side assets. Do not `entity_create(entity="audio_file")` for Suno output until local-file track import exists.
   - Return title, model, payload_mode, source generation/clip ids, file paths, rights/account note, and next actions.

## References

- `reference://suno/models` — model defaults and mode mapping.
- `reference://suno/prompt-craft` — field split, structure tags, sliders, DJ asset recipes.
- `reference://suno/voices` — project voice recipes and formal Suno Voice guardrails.
- `docs/research/2026-07-19-suno-programmatic-deep-research.md` — source research.
- `skills/suno/references/operations.md` — entity/operation matrix.
- `skills/suno/references/troubleshooting.md` — common failures and fixes.

## Stop Conditions

- CAPTCHA/2FA/bot challenge appears.
- User asks to clone a real person's voice without ownership/consent.
- Account lacks model/credits for the requested operation.
- Web upload initialize is required; switch to SunoAPI upload or stop.
