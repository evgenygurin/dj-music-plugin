"""suno_set_asset_workflow — generate self-contained set assets with Suno."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(
    set_id: int,
    asset_plan: str,
    style_hint: str,
    target_dir: str,
) -> str:
    return f"""Generate Suno assets for set {set_id}.

Goal: make the set more self-contained without replacing the real track
program. Use Suno for functional material only: intro beds, outro landings,
short bridge tools, reset loops, spoken-free texture beds, or emergency
rescue loops.

Auth requirement: Suno provider must be registered with no-browser session
auth (`DJ_SUNO_COOKIE_HEADER` or `DJ_SUNO_BEARER_TOKEN`/`DJ_SUNO_CLIENT_TOKEN`
+ `DJ_SUNO_DEVICE_ID`, or a JSON `DJ_SUNO_STORAGE_STATE_PATH`). Do not launch
Playwright/browser-login from this workflow. If Google/Suno requires CAPTCHA
or 2FA, pause and ask the user to refresh session credentials after completing
the check in their browser; do not attempt to bypass it. The provider handles
Suno web auth headers (Cookie `__session`/`__client`, Clerk Bearer token,
browser-token, device-id) internally; do not switch this workflow to a generic
API-key path unless the user explicitly asks for that.

Inputs:
- asset_plan: {asset_plan}
- style_hint: {style_hint}
- target_dir: {target_dir}

1. Inspect the current set:
   local://sets/{set_id}/full
   local://sets/{set_id}/review
   local://sets/{set_id}/cheatsheet

2. Decide assets conservatively:
   - intro: 30-90s, no lead hook that steals identity from track 1.
   - bridge: 16-64 bars, match the surrounding BPM/key/energy and avoid
     melodic claims that fight the next track.
   - outro: 30-120s, de-escalates cleanly and leaves silence/room tone.
   - rescue loop: only for weak/hard transitions that cannot be repaired by
     replace_track_workflow or fix_transition_workflow.

3. For each asset, create one generation:
   provider_write(provider="suno", entity="generation", operation="create",
                  params={{
                    "title": "<set_id>-<slot>-<asset-kind>",
                    "prompt": "<DJ utility prompt: style, BPM, energy, bars, no vocals>",
                    "tags": ["{style_hint}", "dj-tool", "<asset-kind>"],
                    "instrumental": true,
                    "duration_s": <seconds>,
                    "bpm": <target bpm>,
                    "key": "<camelot or musical key if useful>"
                  }})
   Save the returned generation_id. Suno returns a batch of 2-4 variants:
   `generation_id` is the first (already-pollable) clip; `clip_ids` lists all
   variants and `batch_id` the batch. Free-plan default model is
   `chirp-auk-turbo` (set DJ_SUNO_MODEL for a paid model like chirp-fenix).

4. Poll until ready:
   provider_read(provider="suno", entity="generation", id="<generation_id>")
   Continue only when `ready=true` or an audio_url is present. Poll a clip id
   (from `clip_ids`), not the batch id. If it fails, report the failed
   generation_id and generate one alternate with a simpler prompt.

5. Download each ready asset locally:
   provider_write(provider="suno", entity="generation", operation="download",
                  params={{
                    "generation_id": "<generation_id>",
                    "target_dir": "{target_dir}",
                    "title": "<asset-title>"
                  }})

6. Update the deliverable notes:
   - List each generated file_path, intended insertion point, BPM/key intent,
     and whether it is intro/bridge/outro/rescue.
   - Do not call entity_create(entity="audio_file") for Suno assets yet:
     that handler requires existing local track ids. Keep generated files as
     export-side assets until a local-file track import path exists.
   - If the set will be synced to Yandex Music, do not upload generated
     assets through provider_write(provider="yandex", entity="playlist")
     unless the user explicitly asks and rights/account settings allow it.

Return: {{"set_id": {set_id}, "generated_assets": [...],
         "target_dir": "{target_dir}", "manual_cue_notes": [...]}}.
"""


@prompt(
    name="suno_set_asset_workflow",
    description="Generate intro/bridge/outro/rescue audio assets for a set via Suno.",
    tags={"namespace:workflow", "generation", "delivery"},
    meta=PROMPT_META,
)
def suno_set_asset_workflow(
    set_id: int,
    asset_plan: str = "intro, bridges for weak transitions, outro",
    style_hint: str = "hypnotic techno",
    target_dir: str = "generated-sets/suno-assets",
) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(set_id, asset_plan, style_hint, target_dir))],
        description=f"Suno set assets for set {set_id}: {asset_plan}.",
    )
