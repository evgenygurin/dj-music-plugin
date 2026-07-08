"""render_set_workflow — render a set version to a continuous beatmatched mix."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _build_body(version_id: int) -> str:
    return f"""To render set version {version_id} into ONE continuous, beatmatched,
tracks-only DJ mix (EQ bass-swap transitions) and deliver it:

1. Ensure every track has a physical MP3 registered (the engine reads files
   from dj_library_items; it does NOT download). For any missing track:
   entity_create(entity="audio_file", data={{"track_ids": [<track ids>]}})
   Download in batches of ~8-10 under the tool timeout; verify with
   entity_list(entity="audio_file", filters={{"track_id__in": [...]}}).

2. (Recommended) Bring the set tracks to analysis_level=5 first so bpm / key /
   LUFS are accurate:
   entity_update(entity="track_features", id=<track_id>, data={{"level": 5}})

3. Compute the beatgrid (kick-phase + sub-beat phase refine + LUFS level-match):
   render_beatgrid(version_id={version_id})
   Inspect it: read local://render/{version_id}/beatgrid — check per-track
   phase (ms) and gain (dB); tracks flagged "fixed" had a large correction.

4. Render the continuous mix (auto-uses the cached beatgrid):
   render_mixdown(version_id={version_id})
   This is heavy (ffmpeg+rubberband) and runs as a background task; poll
   local://render/jobs/{{job_id}}/status for progress.

5. Verify the mix with automated checks:
   render_verify(version_id={version_id})
   Runs 14 checks: 5 pre-render (source duration, BPM reliability, trim
   bounds, boundary alignment, timeline) + 9 post-render (output duration,
   level jumps, clipping, dropouts, loudness consistency, low-band holes,
   stereo balance, RMS jumps, energy slope).

6. Diagnose the result:
   render_diagnose(version_id={version_id})
   Read local://render/{version_id}/timeline to tell a TRANSITION-window hole
   (a mix defect) from a track's own breakdown (music). Most -17..-20 dB dips
   inside a track body are breakdowns — do NOT chase them.

7. Deliver the portable bundle (source tracks + M3U8 + metadata + MIX.mp3):
   deliver_set(version_id={version_id})
   With emit_continuous_mix enabled the rendered MIX.mp3 ships alongside the
   tracks/ dir, playlist.m3u8, rekordbox.xml, guide.json, and cheatsheet.txt.
   For the full export workflow (rekordbox export + optional YM sync) run
   the deliver_set_workflow prompt instead.

Honest engine limits: no real stem separation (the bass-swap is a 2-band EQ
crossover, not demucs); phrasing is approximate where DB beatgrids are absent;
LOOP_ROLL / FILTER_SWEEP are not engine presets. Target tempo + bar lengths
come from reference://render/defaults."""


@prompt(
    name="render_set_workflow",
    description="Render a set version into a continuous beatmatched DJ mix.",
    tags={"namespace:workflow", "delivery"},
    meta=PROMPT_META,
)
def render_set_workflow(version_id: int) -> PromptResult:
    return PromptResult(
        messages=[Message(_build_body(version_id))],
        description=f"Recipe: render set version {version_id} into a continuous mix.",
    )
