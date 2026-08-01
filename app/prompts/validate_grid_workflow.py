"""validate_grid_workflow — post-render grid-alignment QA + repair decision tree."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _build_body(version_id: int) -> str:
    return f"""Validate version {version_id}'s rendered mix grid alignment.

1. Read the render context:
   local://render/{version_id}/plan        — actual geometry (segments, target_bpm).
   local://render/{version_id}/beatgrid    — per-track trim/phase/bpm_measured.
   local://render/{version_id}/timeline    — segment + transition windows.

2. Run the validator (heavy, background task):
   dj_render_validate_grid(version_id={version_id})
   Read the result: local://render/{version_id}/grid_check.
   Two check layers:
   - plan_checks  — beatgrid bpm_measured vs stored bpm (pre-render drift class).
   - tracks       — each track body's measured BPM in the MIX vs target_bpm
     (proves rubberband honored tempo_ratio = bpm_measured / target).

3. Interpret with the gates (reference://render/validation):
   | |bpm_dev| | meaning                                      |
   |----------|-----------------------------------------------|
   | <= 0.5   | ok — aligned (rubberband residual)            |
   | 0.5-1.0  | warn — audible on long transitions             |
   | > 1.0    | fail — real engine bug (stretch/tempo_ratio)  |

4. Decision tree:
   a. All ok        → grid is aligned; proceed to diagnose/deliver.
   b. fail/warn     → find the root cause on the ORIGINAL audio, NEVER on
      demucs stems (stems shift transients 30-100ms; phase measurements
      there are meaningless):
      1. Re-check bpm on the original MP3:
         compare track_features.audio_bpm vs stored bpm (beatgrid
         bpm_measured comes from the SAME long-window kick detector) —
         if |stored - audio_bpm| > 0.5 the render MUST use audio_bpm.
      2. dj_render_beatgrid(version_id={version_id}, refresh=True) to
         recompute trim/phase/bpm_measured with the correct tempo.
      3. Re-run dj_render_validate_grid — if plan_checks now ok but the
         mix is still off, the bug is in the renderer (report it).
   c. Re-render ONLY if the DSP parameters really changed (subgenre,
      transition_bars/body_bars, effects, levels). Changing just the
      track order or refreshing the grid does NOT need demucs/rubberband
      to rerun — reuse the cached stems.

5. Confirm:
   local://render/{version_id}/grid_check — summary should read "grid OK"
   (or "grid WARN" with a documented, accepted deviation).

Return: {{"version_id": {version_id}, "ok": true|false, "worst_dev_bpm": ...,
         "failed_track_ids": [...], "action_taken": "none|refresh_grid|re-render"}}.
"""


@prompt(
    name="validate_grid_workflow",
    description=(
        "Post-render grid-alignment QA: validate the mix, interpret drift, "
        "decide refresh/re-render."
    ),
    tags={"namespace:workflow", "delivery", "render"},
    meta=PROMPT_META,
)
def validate_grid_workflow(version_id: int) -> PromptResult:
    return PromptResult(
        messages=[Message(_build_body(version_id))],
        description=f"Recipe: validate grid alignment of rendered version {version_id}.",
    )
