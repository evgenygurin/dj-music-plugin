# Suno Claude FastMCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add agent-facing Suno research, Claude Code skill, FastMCP prompt, and read-only references without changing the provider runtime.

**Architecture:** Keep `app/providers/suno` unchanged. Add pure text prompt guidance under `app/prompts`, static JSON reference resources under `app/resources/reference`, and Claude Code operational guidance under `skills/suno`. Tests pin prompt/resource registration and provider entity/operation names.

**Tech Stack:** Python 3.12, FastMCP v3, uv, pytest, ruff/mypy/import-linter, existing Suno provider adapter.

## Global Constraints

- Use `uv` for Python/test commands; do not run `python`, `pytest`, `ruff`, or `mypy` directly.
- Do not add browser automation, Playwright login, CAPTCHA solving, or bot-detection bypass.
- Prompts must remain pure text builders: no repositories, tools, providers, DB, or domain imports.
- Reference resources may import pure domain modules but must not import tools, handlers, or provider adapters.
- Generated Suno files remain export-side assets; do not create `audio_file` rows for them.
- Do not commit unless the user explicitly requests it.

---

## File Structure

- Create `docs/research/2026-07-19-suno-programmatic-deep-research.md`: consolidated external/project research.
- Create `skills/suno/SKILL.md`: concise operational Claude Code skill.
- Create `skills/suno/references/prompt-craft.md`: expanded prompt-craft patterns.
- Create `skills/suno/references/operations.md`: mode-gated operation matrix.
- Create `skills/suno/references/troubleshooting.md`: automation gotchas.
- Create `app/resources/reference/suno.py`: static JSON resources for models, prompt-craft, voices.
- Modify `app/domain/suno_voice/__init__.py`: re-export swallow_boy and taras helpers needed by resources.
- Modify `tests/resources/test_resource_registration.py`: add three `reference://suno/*` URIs and import assertions.
- Create `app/prompts/suno_track_production_workflow.py`: universal Suno production prompt.
- Modify `tests/prompts/test_prompt_registration.py`: register and render the new prompt.
- Modify `tests/prompts/test_prompt_content_correctness.py`: include the new prompt in render/correctness checks.
- Modify `app/prompts/__init__.py`: document generation prompt count.
- Modify `.claude/rules/suno.md`: point to new skill/resources and update research-backed gotchas.

---

### Task 1: Research Document

**Files:**
- Create: `docs/research/2026-07-19-suno-programmatic-deep-research.md`

**Interfaces:**
- Consumes: public docs from Suno help/terms, SunoAPI docs, project `.claude/rules/suno.md`.
- Produces: source-of-truth notes used by skill/resources/prompt.

- [ ] **Step 1: Write the research document**

Create the file with sections:

```markdown
# Suno Programmatic Deep Research

Date: 2026-07-19

## Executive Summary

Use browser-session Suno web mode for the project default no-browser session flow and SunoAPI api_key mode only when `DJ_SUNO_AUTH_MODE=api_key` plus `DJ_SUNO_API_KEY` are present. Treat web-session endpoints as reverse-engineered and version-dependent; treat SunoAPI docs/OpenAPI as the stable gateway contract.

## Sources

- Suno help: `https://help.suno.com/en/categories/550017-making-music`, `https://help.suno.com/en/categories/550145-rights-ownership`, `https://suno.com/terms`.
- SunoAPI docs: `https://docs.sunoapi.org/llms.txt`, `generate-music.md`, `get-music-generation-details.md`, `get-remaining-credits.md`, voice/stem/upload pages.
- FastMCP docs: Context7 `/prefecthq/fastmcp`, prompts/resources with `PromptResult` and decorators.
- Project contract: `.claude/rules/suno.md`.

## Current Model Lineup

SunoAPI documents `V4`, `V4_5`, `V4_5PLUS`, `V4_5ALL`, `V5`, and `V5_5`. V4 is documented as up to 4 minutes; V4.5 variants are documented as up to 8 minutes; V5/V5_5 are current higher-capability models with V5_5 positioned around Voices/custom models. Project web-session mode currently uses `chirp-auk-turbo` as the free-safe default and treats `chirp-fenix`, `chirp-crow`, `chirp-auk`, and `bluejay` as account/plan-dependent keys.

## Two API Surfaces

### Browser Session Web

Host: `https://studio-api-prod.suno.com` plus Clerk auth on `https://auth.suno.com`. Requires user-supplied browser credentials: Cookie, bearer/client token, browser-token, and device-id. Create uses `POST /api/generate/v2-web/` with a flat payload and non-empty `prompt`. Poll with `GET /api/feed/v2/?ids={clip_id}` using clip ids, not the batch id. Download URLs are off-host CDN URLs and must not receive Suno auth headers.

### SunoAPI Gateway

Host: `https://api.sunoapi.org`. Auth is `Authorization: Bearer <DJ_SUNO_API_KEY>`. `POST /api/v1/generate` requires `customMode`, `instrumental`, `callBackUrl`, and `model`; custom vocal mode also requires `style`, `prompt`, and `title`. Each generation returns exactly two songs. Stream URLs usually appear in 30-40 seconds; downloadable URLs in 2-3 minutes. Poll `GET /api/v1/generate/record-info?taskId=...` until `SUCCESS`. Credits via `GET /api/v1/generate/credit`.

## Prompt Engineering

Separate exact lyrics from style/tags. In custom mode, prompt is strict lyrics when vocals are requested; style carries genre, instrumentation, voice, arrangement, BPM/key/bar constraints, and negative tags carry exclusions. Use structure tags such as `[Intro]`, `[Verse]`, `[Hook]`, `[Bridge]`, `[Build]`, `[Drop]`, `[Outro]`; use parenthetical ad-libs sparingly. For DJ assets, prefer instrumental, short bar-counted prompts, explicit BPM/key, no lead hook, and conservative texture language.

## Operational Limits And Rights

SunoAPI generation concurrency is documented as 20 requests per 10 seconds. SunoAPI generation returns two songs. Prompt/style/title character limits depend on model and custom mode. Free-plan Suno songs are non-commercial; songs made while subscribed to paid Pro/Premier plans are granted commercial use rights. Suno terms restrict voice models to the user's own voice and prohibit scraping/circumvention.

## Automation Gotchas

Never automate OAuth/CAPTCHA/2FA. Browser-session bearer lifetime is short and must be refreshed from the user's browser session. Cookie-only auth cannot be assumed to mint a bearer. Web upload initialize is bot-walled; use SunoAPI upload flows for external audio. Web create with empty prompt or missing model can fail; paid model keys can 403 on free accounts. Stems and advanced processing may cost credits and should not be repeated blindly.
```

- [ ] **Step 2: Self-check research scope**

Run: `uv run python -c "from pathlib import Path; p=Path('docs/research/2026-07-19-suno-programmatic-deep-research.md'); s=p.read_text(); assert 'V5_5' in s and 'clip ids' in s and '20 requests per 10 seconds' in s"`

Expected: command exits 0.

---

### Task 2: Suno Reference Resources

**Files:**
- Create: `app/resources/reference/suno.py`
- Modify: `app/domain/suno_voice/__init__.py`
- Modify: `tests/resources/test_resource_registration.py`

**Interfaces:**
- Produces async resources `reference_suno_models() -> str`, `reference_suno_prompt_craft() -> str`, `reference_suno_voices() -> str`.

- [ ] **Step 1: Run impact for exported voice package before modifying**

Run GitNexus impact on `app.domain.suno_voice` or `__init__.py` upstream. If risk is HIGH/CRITICAL, stop and report before editing.

- [ ] **Step 2: Add resource tests first**

Modify `tests/resources/test_resource_registration.py`:

```python
EXPECTED_STATIC_URIS: frozenset[str] = frozenset(
    {
        "schema://entities",
        "schema://providers",
        "session://set-draft",
        "session://tool-history",
        "reference://camelot",
        "reference://subgenres",
        "reference://templates",
        "reference://audit_rules",
        "reference://render/defaults",
        "reference://suno/models",
        "reference://suno/prompt-craft",
        "reference://suno/voices",
    }
)
```

Add import assertions in `test_all_resource_modules_importable`:

```python
assert any(m.endswith(".reference.suno") for m in imported)
```

- [ ] **Step 3: Implement resources**

Create `app/resources/reference/suno.py` with three JSON payloads using `json_dump`, `@resource`, `ANNOTATIONS_READ_ONLY`, and `RESOURCE_META`. Include no provider imports.

- [ ] **Step 4: Re-export voice helpers**

Modify `app/domain/suno_voice/__init__.py` to export swallow_boy and taras constants/functions used by `reference://suno/voices`.

- [ ] **Step 5: Run resource tests**

Run: `uv run pytest tests/resources/test_resource_registration.py -q`

Expected: pass, except existing strict xfail remains xfail.

---

### Task 3: Universal Suno Track Production Prompt

**Files:**
- Create: `app/prompts/suno_track_production_workflow.py`
- Modify: `tests/prompts/test_prompt_registration.py`
- Modify: `tests/prompts/test_prompt_content_correctness.py`
- Modify: `app/prompts/__init__.py`

**Interfaces:**
- Produces prompt function `suno_track_production_workflow(title: str = "Suno Production", brief: str = "", target_dir: str = "suno_out/production", vocal: bool = True, instrumental: bool = False) -> PromptResult`.

- [ ] **Step 1: Run impact for prompt registration tests/files before modifying existing prompt tests**

Run GitNexus impact on `test_all_prompts_return_prompt_result` and `_render` upstream. If risk is HIGH/CRITICAL, stop and report before editing.

- [ ] **Step 2: Add failing prompt registration/content references**

Import `suno_track_production_workflow` in both prompt tests, add it to `EXPECTED_PROMPTS`, `results`, `PROMPTS`, and `_render`.

- [ ] **Step 3: Implement prompt**

Create a pure text prompt using `fastmcp.prompts.Message`, `PromptResult`, `prompt`, and `PROMPT_META`. The body must reference only valid Suno calls: `dj_provider_read(provider="suno", entity="account")`, `dj_provider_write(provider="suno", entity="generation", operation="create")`, `dj_provider_read(provider="suno", entity="generation", id="<generation_id>")`, `dj_provider_write(provider="suno", entity="generation", operation="download")`, and optional valid refinement ops such as `generation.extend`, `generation.concat`, `stem.create`, `wav.create`, `edit.crop`, `edit.fade`, `vocal_removal.create`, `lyrics.create`, `persona.create`, `voice.validate`, `voice.generate`.

- [ ] **Step 4: Update prompt package docs**

Modify `app/prompts/__init__.py` Generation section to list two generation prompts: `suno_set_asset_workflow` and `suno_track_production_workflow`.

- [ ] **Step 5: Run prompt tests**

Run: `uv run pytest tests/prompts/test_prompt_registration.py tests/prompts/test_prompt_content_correctness.py -q`

Expected: pass.

---

### Task 4: Claude Code Suno Skill

**Files:**
- Create: `skills/suno/SKILL.md`
- Create: `skills/suno/references/prompt-craft.md`
- Create: `skills/suno/references/operations.md`
- Create: `skills/suno/references/troubleshooting.md`

**Interfaces:**
- Produces skill name `suno`, discoverable by local Claude/agent tooling.

- [ ] **Step 1: Write skill frontmatter and steps**

Use existing skill style:

```markdown
---
name: suno
description: "Use when generating music with Suno, creating Suno DJ assets, building lyrics/style prompts, voice-locking, extending/concatenating clips, extracting stems/WAV, or debugging Suno auth/model/polling issues. Covers session web mode and sunoapi.org api_key mode."
version: 1.0.0
---

# Suno Production Workflow
```

Then add numbered operational steps for preflight, mode selection, prompt craft, generate, poll, refine, download, rights/auth guardrails, and troubleshooting.

- [ ] **Step 2: Write reference docs**

Create compact reference files for prompt-craft, operations matrix, and troubleshooting. Each must reference `reference://suno/models`, `reference://suno/prompt-craft`, and `.claude/rules/suno.md` where relevant.

- [ ] **Step 3: Sanity-check markdown**

Run: `uv run python -c "from pathlib import Path; paths=list(Path('skills/suno').rglob('*.md')); assert len(paths)==4; assert all('TODO' not in p.read_text() for p in paths)"`

Expected: exits 0.

---

### Task 5: Rules Refresh And Verification

**Files:**
- Modify: `.claude/rules/suno.md`

**Interfaces:**
- Consumes: research doc, skill, resources.
- Produces: updated operational rule pointers.

- [ ] **Step 1: Update rules**

Add near the top a section that points agents to `skills/suno/SKILL.md`, `reference://suno/models`, `reference://suno/prompt-craft`, `reference://suno/voices`, and the research doc. Update current model notes with SunoAPI enums `V4`, `V4_5`, `V4_5PLUS`, `V4_5ALL`, `V5`, `V5_5`.

- [ ] **Step 2: Run targeted tests**

Run: `uv run pytest tests/resources/test_resource_registration.py tests/prompts/test_prompt_registration.py tests/prompts/test_prompt_content_correctness.py tests/domain/suno_voice tests/providers/suno -q`

Expected: pass.

- [ ] **Step 3: Run change impact detection**

Run GitNexus `detect_changes(scope="all", repo="dj-music-plugin")` and verify changed symbols/flows match prompts/resources/skill/docs only.

- [ ] **Step 4: Run broad gate if time allows**

Run: `make check`

Expected: either pass or report pre-existing failures distinctly from Suno changes.
