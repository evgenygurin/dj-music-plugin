"""taste_profile_workflow — curate feedback + affinity to shape scoring."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body() -> str:
    return """Curate the taste memory so set building reflects the DJ's ear.

Two memory layers:
- track_feedback  — per-track verdicts: status in active|liked|banned|archived,
  rating 1-5, plus play_count / skip_count.
- track_affinity  — per-PAIR chemistry: like_count / ban_count / skip_count and
  a net_sentiment derived from played transitions. This is how the engine
  learns which pairings actually work on the floor.

1. Review the current taste state:
   entity_list(entity="track_feedback", filters={"status__in": ["liked","banned"]})
   entity_aggregate(entity="track_feedback", operation="histogram", field="rating")
   entity_list(entity="track_affinity", filters={"net_sentiment__lt": 0})
   — surface loved tracks, banned tracks, and pairings that disappointed.

2. Pull platform signals to bootstrap, if useful:
   provider_read(provider="yandex", entity="likes")    — liked track ids.
   provider_read(provider="yandex", entity="dislikes")  — disliked track ids.
   Map these to local tracks and mirror them into feedback below.

3. Record verdicts (idempotent per track):
   - Love it:  entity_create(entity="track_feedback",
                data={"track_id": <id>, "status": "liked", "rating": 5})
   - Ban it:   entity_create(entity="track_feedback",
                data={"track_id": <id>, "status": "banned"})
   - Adjust:   entity_update(entity="track_feedback", id=<row_id>,
                data={"status": "archived"}) to retire an old verdict.

4. Reinforce or veto pairings (the chemistry layer):
   - A pairing that killed the floor:
     entity_update(entity="track_affinity", id=<row_id>,
                  data={"ban_count": <+1>}) (or create the row if absent via
     entity_create(entity="track_affinity",
                  data={"track_a_id": <a>, "track_b_id": <b>, "ban_count": 1})).
   - A pairing that landed: bump like_count the same way.

5. Verify the loop closes — banned tracks must drop out of suggestions:
   local://tracks/<id>/suggest_next — confirm banned ids no longer appear.
   local://transition_history/best_pairs — confirm your reinforced pairs rank.

Downstream effect: build_set_workflow / scenario_set_workflow / replace_track_
workflow all filter banned tracks and prefer high-affinity pairs, so curating
here steers every future set without touching scoring code.

Return: {"liked": N, "banned": N, "archived": N, "pairs_reinforced": N,
         "pairs_vetoed": N}.
"""


@prompt(
    name="taste_profile_workflow",
    description="Curate track_feedback + track_affinity (like/ban/rate) to steer set scoring.",
    tags={"namespace:workflow", "curation", "feedback"},
    meta=PROMPT_META,
)
def taste_profile_workflow() -> PromptResult:
    return PromptResult(
        messages=[Message(_body())],
        description="Curate taste memory (feedback + affinity) to shape future sets.",
    )
