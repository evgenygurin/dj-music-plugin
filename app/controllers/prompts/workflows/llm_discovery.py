"""Workflow prompt — split from monolithic workflows.py (Phase 10)."""

from typing import Annotated

from fastmcp.prompts import PromptResult, prompt
from pydantic import Field

from app.controllers.prompts.workflow_shared import (
    TRANSITION_SCORING_AND_SEARCH_GUIDE,
    WORKFLOW_PROMPT_VERSION,
    make_prompt_result,
    message_assistant,
    message_user,
)


@prompt(
    name="llm_discovery_workflow",
    title="LLM-Assisted Discovery",
    description="Client-driven discovery: Claude generates search queries, no API key needed",
    tags={"discovery", "workflow"},
    meta={
        "version": WORKFLOW_PROMPT_VERSION,
        "steps": 5,
        "requires_api_key": False,
    },
)
def llm_discovery_workflow(
    track_name: Annotated[
        str, Field(description="Track title or 'Artist - Title' to find similar tracks for")
    ],
    track_id: Annotated[
        int | None, Field(description="Local DB track ID (if known, enables audio feature lookup)")
    ] = None,
    limit: Annotated[int, Field(description="How many similar tracks to find")] = 20,
) -> PromptResult:
    """Client-driven discovery: generate search queries and find similar tracks.

    Steps: Analyze track -> Generate queries -> Call find_similar_tracks -> Review -> Import

    For Claude Code MAX users (no API key needed). Claude generates search queries
    based on track characteristics, then passes them to find_similar_tracks.

    Args:
        track_name: Track title or artist + title
        track_id: Optional local DB track ID (if known)
        limit: How many similar tracks to find
    """
    id_instruction = ""
    if track_id:
        id_instruction = (
            f"\n   - `get_track(id={track_id})` and `get_track_features(id={track_id})` "
            "to get BPM, Camelot key, energy, mood"
        )

    return make_prompt_result(
        [
            message_user(
                f"""Find {limit} tracks similar to "{track_name}" using client-driven discovery.

This workflow does NOT require an API key — you generate the search queries yourself.

Prerequisites: `unlock_tools(category="discovery")` if discovery tools are locked.

Follow these steps:

1. **Analyze the source track**:{id_instruction}
   - Identify key characteristics: BPM range, subgenre, mood, energy level, artists
   - Note the Camelot key for harmonic compatibility

2. **Generate search queries**: Based on the track's style, create 5-10 Yandex Music
   search queries. Mix these approaches:
   - Similar artists in the same subgenre
   - Subgenre + mood keywords (e.g. "dark minimal techno")
   - Labels known for this style (e.g. "Drumcode", "Mord", "Perc Trax")
   - BPM-adjacent styles (if source is 135 BPM, search 130-140 BPM range)

3. **Call find_similar_tracks** with your generated queries:
   ```
   find_similar_tracks(
       track_id={track_id or "<track_id>"},
       strategy="llm",
       search_queries=["query1", "query2", "query3", ...],
       limit={limit}
   )
   ```

4. **Review results**: Check if the similar tracks match the source track's vibe.
   If not enough results, generate more specific queries and call again.

5. **Import**: `import_tracks(track_refs=[<ym_ids>], playlist_id=<id>)` to add the
   best matches to the library.

This is the recommended workflow for Claude Code MAX subscribers (no API key needed).

After imports, if you score DJ pairs or sets, use persisted transitions — reference:
"""
                + "\n"
                + TRANSITION_SCORING_AND_SEARCH_GUIDE
            ),
            message_assistant(
                f'Finding tracks similar to "{track_name}" via client-driven discovery. '
                f"Step 1: analyzing track characteristics"
                f"{f' — `get_track(id={track_id})`' if track_id else ''}...",
            ),
        ],
        description=f"LLM-assisted discovery from '{track_name}'",
    )
