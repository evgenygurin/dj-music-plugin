"""Quick mix compatibility check prompt."""

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
    name="quick_mix_check",
    title="Quick Mix Check",
    description="Check if two tracks mix well together — BPM, key, energy compatibility.",
    tags={"sets", "workflow"},
    meta={"version": WORKFLOW_PROMPT_VERSION, "steps": 3},
)
def quick_mix_check(
    track_a: Annotated[str, Field(description="First track name or ID")],
    track_b: Annotated[str, Field(description="Second track name or ID")],
) -> PromptResult:
    """Quick compatibility check for a pair of tracks."""
    return make_prompt_result(
        [
            message_user(
                f"Check mixing compatibility between '{track_a}' and '{track_b}':\n\n"
                f"1. Resolve both tracks:\n"
                f'   - `get_track(query="{track_a}")`\n'
                f'   - `get_track(query="{track_b}")`\n'
                f"2. Check transition score:\n"
                f"   - `explain_transition(from_track_id=<a_id>, to_track_id=<b_id>)`\n"
                f"3. Summarize: BPM delta, Camelot key compatibility, energy match, "
                f"and a clear recommendation (mix / avoid / conditional)."
            ),
            message_assistant(
                f"Mix check: resolving `{track_a}` and `{track_b}`, then `explain_transition`."
            ),
        ],
        description=f"Mix check: '{track_a}' → '{track_b}'",
    )
