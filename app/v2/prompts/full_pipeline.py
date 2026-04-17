"""full_pipeline — chain expand + build + deliver."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.v2.prompts._shared import PROMPT_META


def _body(playlist_id: int, template: str, sync_to_ym: bool) -> str:
    sync_flag = "true" if sync_to_ym else "false"
    return f"""End-to-end pipeline from playlist {playlist_id} to a delivered set:

Stage 1: Grow the playlist
   Invoke the ``expand_playlist_workflow`` prompt with
   playlist_id={playlist_id}, target_count >= 50. Execute its 10 steps.

Stage 2: Build the set
   Invoke ``build_set_workflow`` with playlist_id={playlist_id},
   template='{template}'. Execute its 8 steps. Capture the returned
   set_id.

Stage 3: Deliver
   Invoke ``deliver_set_workflow`` with set_id=<captured>,
   sync_to_ym={sync_flag}. Execute its 8 steps.

Guardrails:
- If expand failed to reach the candidate pool size, stop and report.
- If build returned quality_score < 0.5, call rebuild/sequence_optimize
  once with tighter constraints before proceeding to deliver.
- If deliver hits a hard conflict, ALWAYS elicit before exporting.

Return: {{"playlist_id": {playlist_id}, "set_id": ..., "version_id": ...,
         "quality_score": ..., "exports": [...]}}.
"""


@prompt(
    name="full_pipeline",
    description="Chain expand -> build -> deliver into a single pipeline.",
    tags={"namespace:workflow", "pipeline"},
    meta=PROMPT_META,
)
def full_pipeline(
    playlist_id: int,
    template: str = "classic_60",
    sync_to_ym: bool = False,
) -> PromptResult:
    return PromptResult(
        messages=[Message(_body(playlist_id, template, sync_to_ym))],
        description=(
            f"Full pipeline: expand playlist {playlist_id} -> build set "
            f"({template}) -> deliver (sync_to_ym={sync_to_ym})."
        ),
    )
