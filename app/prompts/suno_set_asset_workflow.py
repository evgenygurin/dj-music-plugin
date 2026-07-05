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

Auth requirement: Suno provider must be registered. Use the project default
no-browser session auth (`DJ_SUNO_COOKIE_HEADER` or `DJ_SUNO_BEARER_TOKEN` /
`DJ_SUNO_CLIENT_TOKEN` + `DJ_SUNO_DEVICE_ID`, or a JSON
`DJ_SUNO_STORAGE_STATE_PATH`). Do not launch Playwright/browser-login from this
workflow. If Google/Suno requires CAPTCHA or 2FA in session mode, pause and ask
the user to refresh session credentials after completing the check in their
browser; do not attempt to bypass it. SunoAPI mode is supported only as opt-in
when `DJ_SUNO_AUTH_MODE=api_key` + `DJ_SUNO_API_KEY` actually exist.

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
   Save the returned generation_id. In the default web-session mode,
   `generation_id` is the first pollable clip, `clip_ids` lists all variants,
   and `batch_id` is the batch. Web-session model defaults to
   `chirp-auk-turbo`. In opt-in SunoAPI mode, `generation_id` is the taskId;
   poll it until `response.sunoData[]` contains audio variants.

4. Poll until ready:
   provider_read(provider="suno", entity="generation", id="<generation_id>")
   Continue only when `ready=true` or an audio_url is present. In web-session
   mode, poll a clip id (from `clip_ids`), not the batch id. In opt-in SunoAPI
   mode, poll the taskId. If it fails, report the failed generation_id and
   generate one alternate with a simpler prompt.

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

Advanced capabilities (SunoAPI mode only, when `DJ_SUNO_AUTH_MODE=api_key`):
the full sunoapi.org REST surface is available and can refine a raw asset.
Each is a task create (poll it with the matching read entity):
- Rework/lengthen a generated bed:
  provider_write(provider="suno", entity="generation", operation="extend",
                 params={{"audioId": "<clip>", "defaultParamFlag": true,
                          "continueAt": <sec>}})
- Cover/extend an uploaded stem or bed (host it first with
  provider_write(provider="suno", entity="file", operation="upload_url",
                 params={{"fileUrl": "<mp3 url>", "uploadPath": "dj/assets"}}),
  then operation="upload_cover"/"upload_extend" with the returned uploadUrl).
- Stem-split a bed for layering:
  provider_write(provider="suno", entity="vocal_removal", operation="create",
                 params={{"taskId": "<t>", "audioId": "<a>",
                          "type": "split_stem"}})
  then provider_read(provider="suno", entity="vocal_removal", id="<t>").
- WAV master for the USB: entity="wav" operation="create" ->
  provider_read(provider="suno", entity="wav", id="<t>").
Other entities: lyrics, midi, video, cover, persona, style (boost), voice.
Only reach for these when the user asks for more than a plain bed; the DJ
default is instrumental generation + download above.

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
