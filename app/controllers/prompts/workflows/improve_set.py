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
    name="improve_set_workflow",
    title="Improve DJ Set",
    description="Identify and fix weak transitions in an existing DJ set",
    tags={"sets", "workflow"},
    meta={"version": WORKFLOW_PROMPT_VERSION, "steps": 6},
)
def improve_set_workflow(
    set_name: Annotated[str, Field(description="DJ set name or ID to improve")],
) -> PromptResult:
    """Guide through improving an existing DJ set.

    Steps: Review -> Explain weak transitions -> Find replacements -> Rebuild -> Compare -> Iterate

    Args:
        set_name: Name or ID of the set to improve
    """
    return make_prompt_result(
        [
            message_user(
                f"""Improve the quality of DJ set "{set_name}" by identifying and fixing
weak transitions.

Follow these steps:

1. **Review**: `quick_set_review(set_id=<id>)` on "{set_name}" to get:
   - Overall transition quality score
   - Hard conflicts (score = 0.0) — BPM >10, Camelot >=5, or energy >6 LUFS
   - Weak transitions (score < 0.5)
   - Problem areas (sudden energy jumps, key clashes, BPM mismatches)

2. **Explain Problems**: For each weak transition:
   - `explain_transition(from_track_id=<a>, to_track_id=<b>)`
   - Note which component failed: BPM, harmonic, energy, spectral, or groove

3. **Find Replacements**: For problematic tracks:
   - `find_replacement(set_id=<id>, position=<pos>, count=5)`
   - This scores candidates against BOTH neighbors
   - Review top 3-5 suggestions with their combined scores

4. **Rebuild**: `rebuild_set(set_id=<id>, pin=[<good_ids>], exclude=[<bad_ids>],
   algorithm="ga", version_label="improved")` with:
   - pin: tracks with high-scoring transitions (keep them)
   - exclude: problematic tracks (remove them)

5. **Compare**: `compare_set_versions(set_id=<id>)` to verify improvement:
   - Check if overall score increased
   - Verify weak transitions were fixed
   - Ensure no new problems were introduced

6. **Iterate**: If problems remain, repeat steps 2-5 focusing on remaining weak spots

Report score improvements and specific transition fixes after each rebuild."""
            ),
            message_assistant(
                f'Improving "{set_name}". Step 1: `quick_set_review(set_id=<id>)`...',
            ),
        ],
        description=f"Improve DJ set '{set_name}'",
    )
