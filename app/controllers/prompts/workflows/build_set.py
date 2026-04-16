"""Workflow prompt — split from monolithic workflows.py (Phase 10)."""

from typing import Annotated

from fastmcp.prompts import PromptResult, prompt
from pydantic import Field

from app.controllers.prompts.workflow_shared import (
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
4. **Build Set**: `build_set(playlist_id=<id>, name="...", template="{template}",
   algorithm="ga")` — use "greedy" for speed, "ga" for quality
5. **Review**: `quick_set_review(set_id=<id>)` to analyze transitions and energy arc
6. **Fix Problems**: If review shows weak transitions (score < 0.5):
   - `explain_transition(from_track_id=<a>, to_track_id=<b>)` for each weak pair
   - `find_replacement(set_id=<id>, position=<pos>)` for alternatives
   - `rebuild_set(set_id=<id>, pin=<good>, exclude=<bad>, algorithm="ga")`
7. **Deliver**: When satisfied, use `deliver_set` tool or `deliver_set_workflow` prompt

Report progress and findings after each step."""
            ),
            message_assistant(
                f'Building DJ set from "{playlist_name}" ({template}, {duration_min} min). '
                f'Step 1: `get_playlist(query="{playlist_name}", include_tracks=True)`...',
            ),
        ],
        description=(
            f"Build DJ set from '{playlist_name}' using {template} template ({duration_min} min)"
        ),
    )
