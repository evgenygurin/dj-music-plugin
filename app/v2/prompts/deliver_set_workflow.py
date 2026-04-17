"""deliver_set_workflow — export + (optional) YM sync."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.v2.prompts._shared import PROMPT_META


def _build_body(set_id: int, sync_to_ym: bool) -> str:
    sync_clause = (
        "7. Sync the set to the platform as a new playlist:\n"
        "   provider_write(entity='playlist', operation='create_from_set', "
        f"params={{'set_id': {set_id}}})\n"
        if sync_to_ym
        else "7. Skip platform sync (sync_to_ym=false).\n"
    )
    return f"""To deliver set {set_id}:

1. Read the latest version summary:
   local://sets/{set_id}/summary — note version_id and quality_score.

2. Score every transition (fresh, not cached):
   transition_score_pool(track_ids=<ordered track list>)
   — writes fresh rows into the transitions table.

3. Review for hard conflicts:
   local://sets/{set_id}/review — inspect 'hard_conflicts'.

4. If hard_conflicts is non-empty:
   - Use ctx.elicit to ask the user whether to continue or abort.
   - If abort -> stop; if continue -> proceed.

5. Write deliverables:
   - entity_create(entity='app_export', data={{'set_id': {set_id}, 'format': 'm3u8'}})
   - entity_create(entity='app_export', data={{'set_id': {set_id}, 'format': 'rekordbox_xml'}})
   - entity_create(entity='app_export', data={{'set_id': {set_id}, 'format': 'json_guide'}})
   - local://sets/{set_id}/cheatsheet — copy contents for the DJ booth.

6. Copy MP3 files into generated-sets/<name>/ (skipped if iCloud stub).

{sync_clause}
8. Final verification:
   - local://sets/{set_id}/summary (version count increased? quality_score stable?)
   - If any export failed, report file_path=null + error for that format.

Return: {{"set_id": {set_id}, "exports": [...], "ym_playlist_id": ...}}.
"""


@prompt(
    name="deliver_set_workflow",
    description="Recipe: export a set (+ optional YM sync) with a conflict gate.",
    tags={"namespace:workflow", "delivery"},
    meta=PROMPT_META,
)
def deliver_set_workflow(set_id: int, sync_to_ym: bool = False) -> PromptResult:
    return PromptResult(
        messages=[Message(_build_body(set_id, sync_to_ym))],
        description=f"Recipe: deliver set {set_id} (sync_to_ym={sync_to_ym}).",
    )
