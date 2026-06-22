"""analyze_library_workflow — batch-analyze unanalyzed tracks / upgrade tier."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(playlist_id: int | None, level: int, batch_size: int) -> str:
    pool = (
        "First resolve the playlist's track ids — track has no playlist_id\n"
        f"   column — via local://playlists/{playlist_id}?include_tracks=true,\n"
        "   then:\n"
        '   entity_list(entity="track", filters={"id__in": [...playlist ids...], '
        '"has_features": false}, limit=500)'
        if playlist_id is not None
        else 'entity_list(entity="track", filters={"has_features": false}, limit=500)'
    )
    return f"""Bring tracks up to analysis level {level} in batches of {batch_size}.

1. Find tracks missing features (INNER-JOIN gate via has_features):
   {pool}
   — has_features=false yields tracks with no row in
     track_audio_features_computed yet. Page with the returned cursor.

2. (Upgrade path) For tracks that HAVE features but at a lower tier, list
   them and re-run the pipeline higher:
   entity_list(entity="track_features", filters={{"analysis_level__lt": {level}}})
   then entity_update(entity="track_features", id=<track_id>,
                     data={{"level": {level}}})
   — entity_update on track_features dispatches the reanalyze handler.

3. Analyze missing-feature tracks in chunks of {batch_size}:
   entity_create(entity="track_features",
                data={{"track_ids": [...], "level": {level}}})
   — the tiered pipeline runs; mood classification fires automatically at
     level >= 2, writing mood + mood_confidence into the same row.
   - Level 2 = loudness/energy/spectral + librosa BPM/key (fast).
   - Level 3 = full scoring features (set-ready: required by
     transition_score_pool / sequence_optimize).

4. After each chunk, verify progress:
   entity_aggregate(entity="track_features", operation="histogram",
                    field="analysis_level")

5. Report failures: tracks whose features still missing after a chunk
   (no local MP3, decode error) — collect their ids, do NOT retry blindly.
   Downloads happen via entity_create(entity="audio_file", ...) first if a
   track has no physical file.

Guardrails:
- Do not exceed limit=500 per page; respect the returned cursor.
- Level 3 is the floor for set building; only go higher (L4/L5) when a
  template or scoring explicitly needs P1/P2 descriptors.

Return: {{"analyzed": N, "upgraded": N, "failed": [...], "level": {level}}}.
"""


@prompt(
    name="analyze_library_workflow",
    description="Batch-analyze unanalyzed tracks (or upgrade existing) to a target tier.",
    tags={"namespace:workflow", "audio", "analysis"},
    meta=PROMPT_META,
)
def analyze_library_workflow(
    playlist_id: int | None = None,
    level: int = 3,
    batch_size: int = 20,
) -> PromptResult:
    scope = f"playlist {playlist_id}" if playlist_id is not None else "library"
    return PromptResult(
        messages=[Message(_body(playlist_id, level, batch_size))],
        description=f"Batch-analyze {scope} to level {level} (chunks of {batch_size}).",
    )
