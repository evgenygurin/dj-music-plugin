# Suno Claude Code + FastMCP Design

Date: 2026-07-19

## Goal

Создать единый операционный слой для Suno, чтобы Claude Code и FastMCP v3+ использовали уже существующий provider максимально точно: выбирали правильный API surface, не путали session/web и sunoapi.org режимы, безопасно работали с auth, моделями, prompt-craft, voice-lock, polling, refinement и download.

## Existing Context

- Provider уже есть: `app/providers/suno/adapter.py`, `client.py`, `endpoints.py`, `endpoints_web.py`, `session_auth.py`.
- Project default: browser-session Suno web (`studio-api-prod.suno.com`) без Playwright/OAuth в плагине.
- Opt-in gateway: `DJ_SUNO_AUTH_MODE=api_key` + `DJ_SUNO_API_KEY` для `https://api.sunoapi.org`.
- Existing FastMCP prompt `suno_set_asset_workflow` покрывает DJ utility assets, но не универсальный track/voice production.
- Voice recipes уже есть в domain: `rimjoba`, `swallow_boy`, `taras_album`.
- Prompt content tests validate provider entity/operation names against `SunoAdapter`; prompts must remain pure text.
- Reference resources may import pure domain modules and must not import tools/handlers/provider adapters.

## Chosen Approach

Используем один cohesive пакет, а не семейство независимых больших features:

1. Research document as source of truth: `docs/research/2026-07-19-suno-programmatic-deep-research.md`.
2. Claude Code skill: `skills/suno/SKILL.md` plus optional references under `skills/suno/references/`.
3. One universal FastMCP prompt: `suno_track_production_workflow`.
4. Three static reference resources: `reference://suno/models`, `reference://suno/prompt-craft`, `reference://suno/voices`.
5. Rules/docs refresh: `.claude/rules/suno.md`, prompt/resource registration tests, and tool catalog counts where present.

This keeps the runtime provider unchanged and concentrates new value in agent-facing guidance and read-only reference material.

## Components

### Research Document

The document will consolidate current facts from official Suno help/terms, SunoAPI docs/OpenAPI, the existing project rules, and reputable reverse-engineering references. It will explicitly separate:

- Official Suno product facts: rights, model capabilities, Studio features, Voices, Personas, simple/custom mode.
- sunoapi.org gateway contract: API-key auth, model enums, required fields, status polling, callback fields, credit/rate limits.
- Project reverse-engineered web-session contract: Clerk bearer/browser-token/device-id, `v2-web` generation, clip-id polling, CDN download, web-only editing reads/writes, bot-wall constraints.
- Version-dependent claims that may drift.

### Claude Code Skill

`skills/suno/SKILL.md` will be short and operational, matching existing `skills/build-set` style. It will cover:

- Preflight: `provider_read(provider="suno", entity="account")`, identify `payload_mode`, credits, model access.
- Auth rules: never run browser login/Playwright, refresh session token with `uv run python scripts/suno_refresh_token.py` when needed, do not bypass CAPTCHA/2FA.
- Model defaults: session default `chirp-auk-turbo` for free-safe web mode; gateway default selected from available current enums with V5/V5_5 noted as voice/custom-model capable.
- Generation loop: craft prompt, `provider_write(..., entity="generation", operation="create")`, poll the returned clip ids/task id, download only completed URLs.
- Refinement: extend/concat, stems, WAV, crop/fade/reverse, remaster, persona/voice, upload workflows with mode-gating.
- DJ utility assets: intro/outro/bridge/rescue loop constraints for BPM/key/bar count.
- Troubleshooting: empty prompt 403, paid model 403, clip ids vs batch ids, callback optionality, stem bitrate/cost, retention windows.

References will hold deeper prompt-craft and operation matrices so the main skill remains usable.

### FastMCP Prompt

`app/prompts/suno_track_production_workflow.py` will be a pure text prompt returning `PromptResult`. It will not import provider/domain code. It will instruct the model to:

- Read `reference://suno/models`, `reference://suno/prompt-craft`, `reference://suno/voices`.
- Preflight account and mode.
- Build a custom-mode payload for vocals or instrumental generation.
- Poll session clip ids or sunoapi task ids correctly.
- Refine with supported operations only.
- Download and store generated files as export-side assets, not `audio_file` rows.

The existing `suno_set_asset_workflow` remains the narrow DJ-set asset workflow.

### FastMCP Reference Resources

`app/resources/reference/suno.py` will register read-only JSON resources:

- `reference://suno/models`: model names, mode mapping, limits, recommended defaults, source confidence.
- `reference://suno/prompt-craft`: structure tags, style/lyrics split, negative tags, sliders, vocal/persona guidance, techno/DJ asset recipes.
- `reference://suno/voices`: available project voice recipes from pure domain modules, including CLI helpers and cautions.

The resource inventory test must include these URIs.

### Rules And Docs

`.claude/rules/suno.md` will be refreshed to point agents toward the new skill/resources and to update current SunoAPI model/enums and operational gotchas. Docs updates will be minimal and count-focused unless a catalog already has Suno-specific sections.

## Data Flow

1. Agent invokes Suno skill or FastMCP prompt.
2. Agent reads reference resources for models/prompt-craft/voices.
3. Agent checks account/mode via provider read.
4. Agent writes generation request with the correct mode-specific fields.
5. Agent polls by clip ids in session mode or task id in sunoapi mode.
6. Agent refines only after complete output exists.
7. Agent downloads generated URLs to export-side paths.

## Error Handling

- Mode mismatch: skill/prompt require falling back to supported operations or switching auth mode; no blind retries.
- Auth expired: run refresh script or ask user for browser session credentials; never automate OAuth/CAPTCHA.
- Empty prompt: always send non-empty prompt/style as required by surface.
- Paid model blocked: read account models and fall back to free-safe defaults.
- Polling drift: session polls clip ids, gateway polls task ids.
- Upload bot-wall: web upload initialize remains out of bounds; use sunoapi upload workflows when external audio is needed.

## Testing

- Prompt registration tests include `suno_track_production_workflow`.
- Prompt content-correctness tests include the new prompt and validate all provider entity/operation names.
- Resource inventory/import tests include the three new Suno resources.
- Targeted tests: `uv run pytest tests/prompts/test_prompt_registration.py tests/prompts/test_prompt_content_correctness.py tests/resources/test_resource_registration.py`.
- Final local gate where feasible: `make check` or report pre-existing failures clearly.

## Non-Goals

- No new browser automation, Playwright login, CAPTCHA solving, or bot-detection bypass.
- No rewrite of `SunoAdapter` unless tests expose a concrete mismatch.
- No automatic import of generated Suno assets into `audio_file` until local-file track import exists.
- No promise that reverse-engineered web endpoints are stable.
