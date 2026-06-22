"""track_prep_workflow — prepare a single track for mixing, end-to-end."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(track_id: int) -> str:
    return f"""Prepare track {track_id} for mixing — get it set-ready and know
exactly what it mixes with, before it ever lands in a set.

A single-track readiness pass: analyze if needed, audit it against techno
rules, surface its mix numbers, and find compatible neighbours.

1. Identify the track:
   local://tracks/{track_id} — title, artist, duration_ms, status. Confirm it
   is active (status=0), not archived.

2. Ensure it is analyzed to the set-ready floor (level >= 3):
   entity_list(entity="track_features", filters={{"track_id__in": [{track_id}]}},
              fields="scoring")
   — if the row is missing or analysis_level < 3:
     entity_create(entity="track_features",
                  data={{"track_ids": [{track_id}], "level": 3}})
     (runs the tiered pipeline; mood classification fires at level >= 2). If the
     track has no physical MP3, entity_create(entity="audio_file", ...) downloads
     it first.

3. Read the full feature picture:
   local://tracks/{track_id}/features — bpm, bpm_confidence, key_code,
   integrated_lufs, energy_mean, kick_prominence, mood, mood_confidence.
   Map key_code -> Camelot via reference://camelot. Flag risks: low
   bpm_confidence or variable tempo (wobbles ramps), very high/low LUFS
   (energy-hostile to most pools), low mood_confidence (untrusted subgenre).

4. Audit it against the techno rule set:
   local://tracks/{track_id}/audit — passed (bool), violations (list), score.
   Violations tell you where the track is an outlier (e.g. off-genre LUFS,
   atonal, tempo unstable) — useful before trusting it in a journey.

5. Find what it mixes WITH (its mix neighbourhood):
   local://tracks/{track_id}/suggest_next?limit=10 — best outgoing candidates
   (add &energy_direction=up|down|flat to bias). These are the tracks that
   follow {track_id} cleanly; note their BPM/key/mood for crate planning.
   For a specific pairing, local://transition/{track_id}/{{other_id}}/score.

6. Summarize the prep card: ready? (level >= 3, audit passed), the marquee
   numbers (BPM / Camelot / LUFS / mood), any risk flags, and 3-5 strong
   neighbour tracks. Honesty: mix-in/out come from track_sections, not from
   manual hot cues (dj_cue_points is empty).

Return: {{"track_id": {track_id}, "ready": bool, "bpm": ..., "camelot": ...,
         "lufs": ..., "mood": ..., "audit_passed": bool, "risks": [...],
         "neighbours": [...]}}.
"""


@prompt(
    name="track_prep_workflow",
    description="Prep one track for mixing: analyze to L3, audit, show numbers, list neighbors.",
    tags={"namespace:workflow", "analysis", "prep"},
    meta=PROMPT_META,
)
def track_prep_workflow(track_id: int) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(track_id))],
        description=f"Single-track mixing prep for track {track_id}.",
    )
