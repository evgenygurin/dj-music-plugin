"""library_cleanup_workflow — actionable hygiene pass over the library/playlist."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(playlist_id: int | None) -> str:
    scope_resolve = (
        f"   Resolve the playlist's track ids first (track has no playlist_id\n"
        f"   column): local://playlists/{playlist_id}?include_tracks=true ->\n"
        f"   pool_ids = [...]; then scope every filter below to the playlist —\n"
        f'   use "id__in": pool_ids on entity=track filters and\n'
        f'   "track_id__in": pool_ids on entity=track_features filters.\n'
        if playlist_id is not None
        else "   Scope = whole library (omit the track_id__in / id__in clause).\n"
    )
    scope = f"playlist {playlist_id}" if playlist_id is not None else "the library"
    return f"""Run an actionable hygiene pass over {scope}. Unlike
library_health_workflow (which REPORTS distributions), this one finds concrete
problems and prescribes the fix for each.

{scope_resolve}
1. UNANALYZED tracks (no features row — useless for set building):
   entity_list(entity="track", filters={{"has_features": false}}, limit=500)
   entity_aggregate(entity="track", operation="count",
                    filters={{"has_features": false}})
   -> Fix: run analyze_library_workflow to bring them to level >= 3.

2. UNDER-ANALYZED tracks (have features but below set-ready tier 3):
   entity_list(entity="track_features", filters={{"analysis_level__lt": 3}})
   -> Fix: entity_update(entity="track_features", id=<track_id>,
                        data={{"level": 3}})  (dispatches the reanalyze handler).

3. LOW-CONFIDENCE mood labels (classifier was unsure — bad for subgenre
   journeys / style locks):
   entity_list(entity="track_features",
              filters={{"mood_confidence__lte": 0.35}}, fields="scoring")
   -> Fix: re-analyze higher (more features sharpen the classifier), or treat
     the mood as untrusted when planning.

4. TEMPO-SUSPECT tracks (flagged variable, or low BPM detection confidence —
   they wobble ramps and tempo journeys):
   entity_list(entity="track_features",
              filters={{"variable_tempo": true}}, fields="scoring")
   entity_list(entity="track_features", filters={{"bpm_confidence__lte": 0.5}})
   -> Fix: verify BPM by ear; keep them off steep tempo steps.

5. ARCHIVED / inactive tracks cluttering selection (status != active):
   entity_aggregate(entity="track", operation="count",
                    filters={{"status__in": [1]}})
   entity_list(entity="track", filters={{"status__in": [1]}}, fields="summary")
   -> Fix: leave archived (status=1) out of pools, or
     entity_delete(entity="track", id=<id>) only if truly dead (irreversible —
     confirm first; this cascades features/sections).

6. LOUDNESS outliers that will hard-reject on energy (>6 LUFS gap to the pool):
   entity_aggregate(entity="track_features", operation="min_max",
                    field="integrated_lufs")
   entity_aggregate(entity="track_features", operation="histogram",
                    field="integrated_lufs")
   -> Fix: the extreme-quiet / extreme-loud tails are mix-hostile; park them or
     plan deliberate energy resets around them.

7. Summarize as a punch list: {{problem -> count -> recommended action}}.
   Do NOT mass-delete; deletes are irreversible and cascade. Prefer
   re-analysis and pool exclusion over deletion.

Return: {{"scope": "{scope}", "unanalyzed": N, "under_analyzed": N,
         "low_confidence_mood": N, "tempo_suspect": N, "archived": N,
         "loudness_outliers": N, "actions": [...]}}.
"""


@prompt(
    name="library_cleanup_workflow",
    description="Actionable library hygiene: find unanalyzed/low-quality/outlier tracks + fixes.",
    tags={"namespace:workflow", "library", "maintenance"},
    meta=PROMPT_META,
)
def library_cleanup_workflow(playlist_id: int | None = None) -> PromptResult:
    scope = f"playlist {playlist_id}" if playlist_id is not None else "library"
    return PromptResult(
        messages=[Message(_body(playlist_id))],
        description=f"Hygiene punch-list for {scope}.",
    )
