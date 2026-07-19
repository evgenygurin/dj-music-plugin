"""suno_set_asset_workflow — enrich set tracks with Suno:
fill gaps, add texture to monotonous sections, bridge weak transitions."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(
    set_id: int,
    asset_plan: str,
    style_hint: str,
    target_dir: str,
) -> str:
    return f"""Enrich set {set_id} tracks with Suno.

Goal: make every track more interesting throughout its full duration.
Use Suno to **fill silence gaps**, **add background texture to monotonous
sections**, and **bridge weak transitions** — NOT to create standalone
intro/outro beds. The real tracks ARE the program; Suno only patches
what is missing or thin.

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

1. Inspect the set and read the REAL per-track descriptors (never invent them):
   local://sets/{set_id}/full
   local://sets/{set_id}/review
   local://sets/{set_id}/cheatsheet
   These carry each track's mood, BPM, key (Camelot / key_code) and LUFS.
   Anchor every Suno prompt to these real numbers; {style_hint} is only a
   fallback when a slot has no neighbouring track to match.

2. Derive a matched brief per asset from the NEIGHBOURING tracks (DB-driven):
   - gap_fill  -> find silence or near-silence sections in a track (RMS < -40 dB,
               spectral flux near zero). Generate a short bed (8-32 bars) at the
               track's own BPM/key/mood that fills the hole without stealing focus.
   - texture   -> detect monotonous stretches (low spectral novelty, flat energy
               over >32 bars). Generate an ambient/dub texture bed at matched
               BPM/key that sits underneath, adding movement without a lead hook.
   - bridge    -> average the two tracks around a weak/hard transition: BPM
               between them, key compatible with both (Camelot +/-1), energy
               between their LUFS.
   - rescue    -> match the two tracks of a failing transition.
   Map the project mood to Suno style tags + a library-measured BPM band:
     dub_techno / ambient_dub ~123-125 (deep, spacious, dub chords, tape echo)
     minimal ~126-128 (stripped, hypnotic, tight kick)
     detroit ~127 (warm strings, machine soul)
     melodic_deep / progressive ~124-126 (warm pads, emotive)
     driving ~126 (rolling 909, propulsive)   hypnotic ~125 (repetitive, tunnel)
     tribal ~129 (percussive)   peak_time ~132 (big, festival)
     acid ~126 (303 resonance)   industrial ~125 (distorted, metallic)
     raw ~139   hard_techno ~136 (fast, pounding)
   Keep assets conservative: gap_fill 8-32 bars (no lead hook), texture 16-64 bars
   (ambient bed, no drums unless the original is drum-thin), bridge 16-64 bars,
   rescue only where replace_track_workflow / fix_transition_workflow cannot repair.

3. For each asset, create one generation with the DERIVED brief:
   dj_provider_write(provider="suno", entity="generation", operation="create",
                  params={{
                    "title": "<set_id>-<slot>-<asset-kind>",
                    "prompt": "<derived: mood + BPM + key + energy + bars, no vocals>",
                    "tags": ["<derived mood/style tags>", "dj-tool", "<asset-kind>"],
                    "instrumental": true,
                    "duration_s": <seconds>,
                    "bpm": <derived target bpm>,
                    "key": "<neighbour Camelot/key>"
                  }})
   Save the returned generation_id. In the default web-session mode,
   `generation_id` is the first pollable clip, `clip_ids` lists all variants,
   and `batch_id` is the batch. Web-session model defaults to
   `chirp-auk-turbo`. In opt-in SunoAPI mode, `generation_id` is the taskId;
   poll it until `response.sunoData[]` contains audio variants.

4. Poll until ready:
   dj_provider_read(provider="suno", entity="generation", id="<generation_id>")
   Continue only when `ready=true` or an audio_url is present. In web-session
   mode, poll a clip id (from `clip_ids`), not the batch id. In opt-in SunoAPI
   mode, poll the taskId. If it fails, report the failed generation_id and
   generate one alternate with a simpler prompt.

5. Download each ready asset locally:
   dj_provider_write(provider="suno", entity="generation", operation="download",
                  params={{
                    "generation_id": "<generation_id>",
                    "target_dir": "{target_dir}",
                    "title": "<asset-title>"
                  }})

6. Update the deliverable notes:
   - List each generated file_path, intended insertion point, BPM/key intent,
     and whether it is gap_fill/texture/bridge/rescue.
   - Do not call dj_entity_create(entity="audio_file") for Suno assets yet:
     that handler requires existing local track ids. Keep generated files as
     export-side assets until a local-file track import path exists.
   - If the set will be synced to Yandex Music, do not upload generated
     assets through dj_provider_write(provider="yandex", entity="playlist")
     unless the user explicitly asks and rights/account settings allow it.

Web-mode polish (default browser session — all verified live). Refine a raw
generated bed with the Suno web ops; each derived clip is downloaded the same
way as step 5 (pass its `generation_id`/`audio_url`):
- Longer bed: extend, then merge the chain into one clip:
  dj_provider_write(provider="suno", entity="generation", operation="extend",
                 params={{"continue_clip_id": "<clip>", "continue_at": <sec>,
                          "prompt": "<derived brief>"}})
  dj_provider_write(provider="suno", entity="generation", operation="concat",
                 params={{"clip_id": "<extension clip>"}})
- 4-deck layering tools: split a bed into stems (returns Vocals + Instrumental
  clips; poll each with a generation read, then download):
  dj_provider_write(provider="suno", entity="stem", operation="create",
                 params={{"clip_id": "<clip>"}})
- USB WAV master: convert, then read the WAV url and download it:
  dj_provider_write(provider="suno", entity="wav", operation="create",
                 params={{"clip_id": "<clip>"}})
  dj_provider_read(provider="suno", entity="clip", id="<clip>",
                params={{"kind": "wav"}})
- Trim to an exact slot length (each returns a pollable clip in `generation_id`):
  dj_provider_write(provider="suno", entity="edit", operation="crop",
                 params={{"clip_id": "<clip>", "crop_start_s": <s>, "crop_end_s": <e>}})
  dj_provider_write(provider="suno", entity="edit", operation="fade",
                 params={{"clip_id": "<clip>", "fade_in_time": <s>, "fade_out_time": <s>}})

Advanced capabilities (SunoAPI mode only, when `DJ_SUNO_AUTH_MODE=api_key`):
the full sunoapi.org REST surface is available and can refine a raw asset.
Each is a task create (poll it with the matching read entity):
- Rework/lengthen a generated bed:
  dj_provider_write(provider="suno", entity="generation", operation="extend",
                 params={{"audioId": "<clip>", "defaultParamFlag": true,
                          "continueAt": <sec>}})
- Cover/extend an uploaded stem or bed (host it first with
  dj_provider_write(provider="suno", entity="file", operation="upload_url",
                 params={{"fileUrl": "<mp3 url>", "uploadPath": "dj/assets"}}),
  then operation="upload_cover"/"upload_extend" with the returned uploadUrl).
- Stem-split a bed for layering:
  dj_provider_write(provider="suno", entity="vocal_removal", operation="create",
                 params={{"taskId": "<t>", "audioId": "<a>",
                          "type": "split_stem"}})
  then dj_provider_read(provider="suno", entity="vocal_removal", id="<t>").
- WAV master for the USB: entity="wav" operation="create" ->
  dj_provider_read(provider="suno", entity="wav", id="<t>").
Other entities: lyrics, midi, video, cover, persona, style (boost), voice.
Only reach for these when the user asks for more than a plain bed; the DJ
default is instrumental generation + download above.

Return: {{"set_id": {set_id}, "generated_assets": [...],
         "target_dir": "{target_dir}", "manual_cue_notes": [...]}}.
"""


@prompt(
    name="suno_set_asset_workflow",
    description=(
        "Enrich set tracks via Suno: "
        "fill gaps, add texture to monotonous sections, bridge weak transitions."
    ),
    tags={"namespace:workflow", "generation", "delivery"},
    meta=PROMPT_META,
)
def suno_set_asset_workflow(
    set_id: int,
    asset_plan: str = (
        "gap fills for silence, texture for monotonous sections, bridges for weak transitions"
    ),
    style_hint: str = "hypnotic techno",
    target_dir: str = "generated-sets/suno-assets",
) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(set_id, asset_plan, style_hint, target_dir))],
        description=f"Suno track enrichment for set {set_id}: {asset_plan}.",
    )
