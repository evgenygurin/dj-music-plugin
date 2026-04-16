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
    name="deliver_set_workflow",
    title="Deliver DJ Set",
    description="Export a completed DJ set: score, handle conflicts, generate files, YM sync",
    tags={"delivery", "workflow"},
    meta={"version": WORKFLOW_PROMPT_VERSION, "steps": 7},
)
def deliver_set_workflow(
    set_name: Annotated[str, Field(description="DJ set name or ID to deliver")],
    sync_ym: Annotated[
        bool, Field(description="Whether to sync set to Yandex Music playlist")
    ] = False,
) -> PromptResult:
    """Guide through delivering a completed DJ set.

    Steps: Score -> Handle conflicts -> Export -> Copy files -> Verify -> Cheat sheet -> YM sync

    Args:
        set_name: Name or ID of the set to deliver
        sync_ym: Whether to sync to Yandex Music playlist
    """
    sync_note = (
        "\n7. **Platform Sync**: `push_set_to_platform(set_id=<id>)` "
        "to push the set to the active platform"
        if sync_ym
        else ""
    )

    return make_prompt_result(
        [
            message_user(
                f"""Deliver the completed DJ set "{set_name}" with all export formats
and optional Yandex Music sync.

Prerequisites: `unlock_tools(category="delivery")` if delivery tools are locked.

Follow these steps:

1. **Score All Transitions**: `score_transitions(mode="set", set_id=<id>)` to:
   - Calculate all consecutive pair scores
   - Identify any hard conflicts (score = 0.0)
   - Get overall quality metrics (avg, min, weak count)

2. **Handle Conflicts**: If hard conflicts exist:
   - `explain_transition(from_track_id=<a>, to_track_id=<b>)` on each conflicting pair
   - Either: `find_replacement(set_id=<id>, position=<pos>)` to fix them
   - Or: continue with conflicts if user accepts (elicitation will ask)

3. **Deliver**: `deliver_set(set_id=<id>, copy_files=True, sync_to_ym={sync_ym},
   formats=["m3u8", "json_guide", "cheat_sheet"])`:
   - Handle any elicitation prompts (conflict warnings, YM playlist exists, etc.)

4. **Verify Exports**: Check that all files were created in generated-sets/:
   - Numbered MP3 files (01. Track.mp3, 02. Track.mp3, ...)
   - M3U8 playlist with DJ extension tags (BPM, key, cue points, transitions)
   - JSON guide (detailed per-track and per-transition info)
   - Text cheat sheet (human-readable transition notes)

5. **Check iCloud**: Report any iCloud stub warnings (files not downloaded)
   - Note which tracks need manual download from iCloud

6. **Get Cheat Sheet**: `get_set_cheat_sheet(set_id=<id>)` for quick DJ reference
   - Shows transition types, scores, BPM/key changes, flagged problems{sync_note}

The set is ready for import into your DJ software (Traktor, Rekordbox, djay).
Report the output directory path and any warnings."""
            ),
            message_assistant(
                f'Delivering "{set_name}". '
                f"{'Will sync to Yandex Music after export. ' if sync_ym else ''}"
                'Step 1: `score_transitions(mode="set", set_id=<id>)`...',
            ),
        ],
        description=f"Deliver set '{set_name}'" + (" with YM sync" if sync_ym else ""),
    )
