"""Workflow prompt — split from monolithic workflows.py (Phase 10)."""

from typing import Annotated

from fastmcp.prompts import PromptResult, prompt
from pydantic import Field

from app.controllers.prompts.workflow_shared import (
    DRAFT_STATELESS_GUIDE,
    TRANSITION_SCORING_AND_SEARCH_GUIDE,
    WORKFLOW_PROMPT_VERSION,
    make_prompt_result,
    message_assistant,
    message_user,
)


@prompt(
    name="build_set_workflow",
    title="Build DJ Set",
    description="Step-by-step: build an optimized DJ set from a playlist",
    tags={"sets", "workflow"},
    meta={"version": WORKFLOW_PROMPT_VERSION, "steps": 7},
)
def build_set_workflow(
    playlist_name: Annotated[str, Field(description="Playlist name or ID to build set from")],
    template: Annotated[
        str,
        Field(
            description=(
                "Set template: classic_60, peak_hour_60, roller_90,"
                " progressive_120, wave_120, closing_60"
            ),
        ),
    ] = "classic_60",
    duration_min: Annotated[int, Field(description="Target set duration in minutes")] = 60,
) -> PromptResult:
    """Guide through building a DJ set from scratch.

    Steps: Get playlist -> Audit -> Fill gaps -> Build -> Review -> Fix -> Deliver

    Args:
        playlist_name: Playlist name or ID to build set from
        template: Set template name (classic_60, peak_hour_60, etc.)
        duration_min: Target duration in minutes
    """
    return make_prompt_result(
        [
            message_user(
                f"""Build a DJ set from playlist "{playlist_name}" using the "{template}" template
with target duration {duration_min} minutes.

Follow these steps:

1. **Get Playlist**: `get_playlist(query="{playlist_name}", include_tracks=True)`
2. **Audit Playlist**: `audit_playlist(playlist_query="{playlist_name}")` to check
   track quality, mood distribution, BPM range, and energy coverage
3. **Fill Gaps**: If audit shows missing moods/energy levels:
   - `find_similar_tracks(track_id=<seed>, strategy="ym")` for each gap
   - Or use `llm_discovery_workflow` prompt for LLM-assisted discovery
4. **Build Set (Declarative)**:
   - `get_candidate_pool(...)` -> choose and order tracks manually
   - Optional fast precompute inside pool: `score_transitions(mode="subset", track_ids=[...], top_n=50)`
   - `preview_set_arc(track_ids=[...], template="{template}")`
   - `search_transitions(limit=500, include_fields="from_track_id,to_track_id,overall_quality,hard_reject", target_quality=0.95)`
   - If `quality_guardrail.meets_target=false`, lower target or expand candidate pool before iterating
   - iterate ordering until arc stabilizes; then `commit_draft(track_ids=[...], set_name="...", template="{template}")`
5. **Review**:
   - `score_transitions(mode="set", set_id=<id>, include_transitions=true, transitions_limit=200)`
   - `quick_set_review(set_id=<id>)` for transition and problem flags
6. **Fix Problems**: If review shows weak transitions:
   - `explain_transition(from_track_id=<a>, to_track_id=<b>)` for each weak pair
   - `find_replacement(set_id=<id>, position=<pos>)` for alternatives
   - reorder and re-check via `preview_set_arc` / `score_transitions`
7. **Deliver**: When satisfied, use `deliver_set` tool or `deliver_set_workflow` prompt

Report progress and findings after each step.

"""
                + TRANSITION_SCORING_AND_SEARCH_GUIDE
                + "\n\n"
                + DRAFT_STATELESS_GUIDE
            ),
            message_assistant(
                f'Building DJ set from "{playlist_name}" ({template}, {duration_min} min). '
                f'Step 1: `get_playlist(query="{playlist_name}", include_tracks=True)`, '
                f'then feasibility gate via `search_transitions(..., target_quality=0.95)`...',
            ),
        ],
        description=(
            f"Build DJ set from '{playlist_name}' using {template} template ({duration_min} min)"
        ),
    )
