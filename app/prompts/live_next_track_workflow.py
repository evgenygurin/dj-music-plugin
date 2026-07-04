"""live_next_track_workflow — mid-set live decision: what to play next."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(last_track_id: int, energy_direction: str) -> str:
    return f"""You are mixing LIVE. The track now playing is {last_track_id}.
Pick the next track to drop — read the room, do not pre-plan a whole set.

This is the live performance loop (call it again after each track), not
build_set_workflow (whole set up front) nor extend_set_workflow (append to a
persisted set). Nothing is persisted here; it is an in-the-moment decision.

1. Read the live state:
   session://set-draft — what is already played this session + target_duration_ms
   (how much time is left to fill).
   session://energy-trend?limit=8 — the recent LUFS samples. Rising samples =
   the floor is climbing (lean energy_direction='up'); a long plateau = time to
   either lift or breathe; falling = you are in a cool-down.
   session://tool-history — what you just did, to avoid repeating a pick.

2. Confirm the energy intent for THIS pick. The caller asked for
   '{energy_direction}' — reconcile it with the trend:
   - 'up'   -> climb (next track ~+0.5 LUFS, same/closer BPM, key +1 or A<->B).
   - 'flat' -> hold the groove (same energy band, vary texture: bright<->dark).
   - 'down' -> ease off (lower LUFS, longer blend, deeper subgenre).

3. Get candidates that mix OUT of the current track:
   local://tracks/{last_track_id}/suggest_next?limit=12&energy_direction={energy_direction}
   — candidates already respect BPM/key/energy adjacency from {last_track_id}.
   (energy_direction is validated server-side to up|down|flat.)

4. Filter the candidates fast:
   - drop banned tracks:
     entity_list(entity="track_feedback", filters={{"status": "banned"}})
   - confirm they are set-ready (level >= 3) and inspect the marquee numbers:
     entity_list(entity="track_features", filters={{"track_id__in": [...]}},
                fields="scoring")  — bpm, key_code, integrated_lufs, mood.
   - prefer tracks you have NOT already played this session (session://set-draft).
   - if any filter/payload is uncertain, read schema://entities/track_features.
   - mood is a hint, not ground truth: confirm the live choice with BPM, LUFS,
     energy_mean, spectral balance, hp_ratio and Beatport genre.
   - if Beatport genre conflicts with classifier mood, mention the risk instead
     of pretending the style label is certain.

5. Vet the top 1-2 picks as a real transition before committing:
   local://transition/{last_track_id}/{{candidate_id}}/score — overall must clear
   hard_reject; read /explain if a component looks weak. (Or run the
   quick_mix_check prompt for a fuller a->b read.)
   For raw/hypnotic or low key_confidence material, use groove-first judgment:
   BPM, low-end, energy and percussion continuity can outweigh Camelot.

6. Commit the human call: give 2-3 options, then name ONE next track + the mix
   technique to use (long blend / bass-swap / echo-out), and a backup pick.
   Honesty: mix points come from track_sections (auto), not manual hot cues —
   phrase-align by ear. Do not promise local delivery unless audio_file /
   physical MP3 exists.

Return: {{"now_playing": {last_track_id}, "energy_direction": "{energy_direction}",
         "next_track_id": ..., "technique": ..., "backup_track_id": ...,
         "reason": ...}}.
"""


@prompt(
    name="live_next_track_workflow",
    description="Live mid-set decision: pick the next track from the current one + room energy.",
    tags={"namespace:workflow", "live", "performance"},
    meta=PROMPT_META,
)
def live_next_track_workflow(
    last_track_id: int,
    energy_direction: str = "flat",
) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(last_track_id, energy_direction))],
        description=(f"Live next-track pick after {last_track_id} (energy '{energy_direction}')."),
    )
