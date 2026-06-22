"""playlist_sync_workflow — pull/push/diff a playlist against Yandex Music."""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.prompts._shared import PROMPT_META


def _body(playlist_id: int, direction: str) -> str:
    return f"""Synchronise playlist {playlist_id} with Yandex Music
(direction='{direction}').

Sync directions:
- diff  -> compute the delta only (read-only, no writes). Always start here.
- pull  -> apply the remote state to the local playlist.
- push  -> apply the local state to the remote playlist.

1. ALWAYS preview first (never blind-write):
   playlist_sync(playlist_id={playlist_id}, direction="diff", source="yandex",
                dry_run=true)
   — returns {{added, removed, reordered}} without touching anything.

2. Inspect both sides so the diff makes sense:
   local://playlists/{playlist_id}?include_tracks=true — local order + ids.
   provider_read(provider="yandex", entity="playlist", id="<remote_id>") —
   remote tracks + current revision (YM revisions change on every edit).

3. Gate on surprises BEFORE applying:
   - Large removals (push deleting many remote tracks) or a remote that drifted
     far from local -> pause and confirm with the user (elicit) rather than
     auto-applying. Destructive divergence is the #1 sync footgun.
   - On 'pull', new remote tracks may be absent locally: import them first
     (entity_create(entity="track", data={{"source": "yandex",
     "external_ids": [...]}})) so the local playlist can reference real rows.

4. Apply the chosen direction once confirmed:
   playlist_sync(playlist_id={playlist_id}, direction="{direction}",
                source="yandex", dry_run=false)
   — for 'push'/'pull' the handler builds the YM JSON diff (insert/delete
     ops + revision) under the hood; you do not hand-craft the diff.

5. Re-fetch to confirm convergence (YM bumps the revision on every write):
   provider_read(provider="yandex", entity="playlist", id="<remote_id>")
   playlist_sync(playlist_id={playlist_id}, direction="diff", source="yandex",
                dry_run=true) — the diff should now be empty.

Return: {{"playlist_id": {playlist_id}, "direction": "{direction}",
         "added": N, "removed": N, "reordered": N, "applied": true|false,
         "converged": true|false}}.
"""


@prompt(
    name="playlist_sync_workflow",
    description="Pull/push/diff a local playlist against Yandex Music with a conflict gate.",
    tags={"namespace:workflow", "sync"},
    meta=PROMPT_META,
)
def playlist_sync_workflow(playlist_id: int, direction: str = "diff") -> PromptResult:
    return PromptResult(
        messages=[Message(_body(playlist_id, direction))],
        description=f"Sync playlist {playlist_id} with YM (direction={direction}).",
    )
