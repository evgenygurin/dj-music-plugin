"""suno_track_production_workflow — full Suno track / vocal production guide."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(
    title: str,
    brief: str,
    target_dir: str,
    vocal: bool,
    instrumental: bool,
) -> str:
    mode = "instrumental" if instrumental else "vocal" if vocal else "general"
    rendered_brief = brief or "derive a concise musical brief from the user's request"
    return f"""Produce a Suno track with maximum programmatic accuracy.

Title: {title}
Mode: {mode}
Brief: {rendered_brief}
Target directory: {target_dir}

Mandatory references before creating anything:
- reference://suno/models
- reference://suno/prompt-craft
- reference://suno/voices
- .claude/rules/suno.md when debugging provider behaviour

Hard boundaries:
- Do not launch Playwright/browser-login/OAuth from this workflow.
- Do not bypass CAPTCHA, 2FA, Cloudflare, or any bot-detection.
- Generated files are export-side assets; do not call
  entity_create(entity="audio_file") for them.
- If commercial use matters, verify account plan/rights first. Free-plan Suno
  output is non-commercial; paid-plan output is governed by Suno terms.

1. Preflight account and provider mode.
   provider_read(provider="suno", entity="account")
   Capture `payload_mode`, credits, plan, and available models. If the provider
   is not registered or credentials are expired, ask the user to refresh their
   browser session credentials. In this project the refresh path is:
   `uv run python scripts/suno_refresh_token.py`.

2. Pick the API path.
   - session / suno_web: use browser-session mode with `chirp-auk-turbo` unless
     account models explicitly allow another key. Web-session create returns
     clip ids; poll clip ids, not the batch id.
   - sunoapi: use API-key mode only when `DJ_SUNO_AUTH_MODE=api_key` and
     `DJ_SUNO_API_KEY` exist. Use documented models (`V4`, `V4_5`, `V4_5PLUS`,
     `V4_5ALL`, `V5`, `V5_5`). Use `V5_5` for Suno Voice / voice_persona work.

3. Craft the payload.
   - For vocals: lyrics go in `prompt`; style/genre/voice/BPM/key/arrangement go
     in `tags` or `style`; use structure tags like [Intro], [Verse], [Hook],
     [Bridge], [Build], [Drop], [Outro].
   - For instrumental DJ tools: set instrumental true; include BPM, key/Camelot,
     bar count, loopability, no vocal, no lead hook, clean mix handles.
   - For voice-lock: use the full voice block from reference://suno/voices and
     change only the genre tail. Do not create Persona/Voice unless explicitly
     requested; formal Suno Voice must only use the user's own voice.

4. Create one generation.
   provider_write(provider="suno", entity="generation", operation="create",
                  params={{
                    "title": "{title}",
                    "prompt": "<non-empty lyrics or musical brief>",
                    "tags": "<style, voice, genre, BPM/key, arrangement>",
                    "instrumental": {str(instrumental).lower()},
                    "negative_tags": "<broad exclusions>",
                    "model": "<account-supported model>"
                  }})
   In sunoapi custom mode, include `customMode`, `style`, `title`, `model`,
   `instrumental`, and `callBackUrl` as required by the gateway contract.

5. Poll until ready.
   provider_read(provider="suno", entity="generation", id="<generation_id>")
   - session mode: poll each returned `clip_ids` entry; `batch_id` is not a feed id.
   - sunoapi mode: poll the task id until `SUCCESS` and `response.sunoData[]` has
     audioUrl entries.
   Stop on explicit failure states and report the raw error/status.

6. Choose the best variant.
   Evaluate musical fit first: prompt adherence, voice identity, BPM/key intent,
   arrangement cleanliness, intro/outro handles, and moderation/errors. Avoid
   repeated expensive retries; simplify the prompt before retrying.

7. Refine only when the mode supports it.
   Web-session refinements:
   provider_write(provider="suno", entity="generation", operation="extend",
                  params={{"continue_clip_id": "<clip>", "continue_at": <sec>,
                           "prompt": "<continuation brief>"}})
   provider_write(provider="suno", entity="generation", operation="concat",
                  params={{"clip_id": "<extension clip>"}})
   provider_write(provider="suno", entity="stem", operation="create",
                  params={{"clip_id": "<clip>"}})
   provider_write(provider="suno", entity="wav", operation="create",
                  params={{"clip_id": "<clip>"}})
   provider_write(provider="suno", entity="edit", operation="crop",
                  params={{"clip_id": "<clip>", "crop_start_s": <s>,
                           "crop_end_s": <s>}})
   provider_write(provider="suno", entity="edit", operation="fade",
                  params={{"clip_id": "<clip>", "fade_in_time": <s>,
                           "fade_out_time": <s>}})

   SunoAPI refinements:
   provider_write(provider="suno", entity="vocal_removal", operation="create",
                  params={{"taskId": "<task>", "audioId": "<audio>",
                           "type": "separate_vocal"}})
   provider_write(provider="suno", entity="lyrics", operation="create",
                  params={{"prompt": "<lyrics brief>"}})
   provider_write(provider="suno", entity="persona", operation="create",
                  params={{"taskId": "<task>", "audioId": "<audio>"}})
   provider_write(provider="suno", entity="voice", operation="validate",
                  params={{"voiceName": "<user-owned voice name>"}})
   provider_write(provider="suno", entity="voice", operation="generate",
                  params={{"taskId": "<validation task>",
                           "verifyUrl": "<user singing verification url>"}})

8. Download final assets.
   provider_write(provider="suno", entity="generation", operation="download",
                  params={{
                    "generation_id": "<ready clip or task id>",
                    "target_dir": "{target_dir}",
                    "title": "{title}"
                  }})

Return a concise production report:
{{"title": "{title}", "mode": "{mode}", "target_dir": "{target_dir}",
  "chosen_generation_id": "...", "downloaded_files": [...],
  "model": "...", "payload_mode": "...", "next_actions": [...]}}.
"""


@prompt(
    name="suno_track_production_workflow",
    description=(
        "Produce a Suno track with correct mode preflight, prompt craft, "
        "polling, refinement, and download."
    ),
    tags={"namespace:workflow", "generation", "suno"},
    meta=PROMPT_META,
)
def suno_track_production_workflow(
    title: str = "Suno Production",
    brief: str = "",
    target_dir: str = "suno_out/production",
    vocal: bool = True,
    instrumental: bool = False,
) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(title, brief, target_dir, vocal, instrumental))],
        description=f"Suno production workflow for {title}.",
    )
