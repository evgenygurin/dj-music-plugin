"""Shared helpers for MCP workflow prompts (FastMCP ``@prompt``).

Runtime-checked API (fastmcp 3.2.x): ``Message(content, role='user'|'assistant')``,
``PromptResult(messages=[...], description='...')``.

External ``search_docs`` had no excerpts in this environment; helpers mirror the
installed package behaviour only.
"""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult

# Increment when prompt semantics or tool references change meaningfully.
WORKFLOW_PROMPT_VERSION = "1.5"

# Reference for workflows / session bootstrap — keep in sync with ``sets`` tools.
TRANSITION_SCORING_AND_SEARCH_GUIDE = """
---
### Tools: persisted transitions (table ``transitions``)

**``score_transitions``** (writes / refreshes DB rows)
- Default ``mode`` is ``"set"``. Wrong mode or missing ids → validation error.
- ``mode="pair"`` + ``from_track_id``, ``to_track_id`` — score and persist one edge.
- ``mode="set"`` + ``set_id`` — all consecutive pairs in the set's **latest** version.
  Response may omit the ``transitions`` list unless ``include_transitions=true`` (keeps
  payloads small). With ``include_transitions=true``: slice via ``transitions_limit``,
  ``transitions_offset``; tool adds ``transitions_total``, ``transitions_truncated``,
  ``transitions_next_offset``, ``transitions_included`` as applicable.
- ``mode="track_candidates"`` + ``track_id`` + ``count`` (alias ``top_n``, default 10) — ranked neighbor
  candidates for one anchor (exploration, not a full-table dump).
- ``mode="subset"`` + ``track_ids`` + ``count`` (alias ``top_n``) — score all directed pairs inside
  an explicit filtered pool (use this after candidate prefiltering to avoid all-vs-all).

**``search_transitions``** (read persisted rows; no rescoring)
- Pagination: ``limit`` in 1-500, ``offset`` >= 0. Response: ``rows``, ``total``,
  ``returned``, ``next_offset``, ``truncated``, ``sort``, ``filters_applied``, ``fields``;
  optional ``stats``, optional ``quality_guardrail``; ``filter_operators`` only if
  ``include_field_catalog=true``.
- Sort: ``sort_by`` comma-separated; token ``+col`` = ASC, ``-col`` = DESC. Tokens
  without prefix use ``sort_order`` (``asc``|``desc``) or ``sort_direction`` (alias;
  overrides ``sort_order`` for those tokens). Default ``sort_by``: ``-overall_quality``.
- ``filters``: shorthand equality ``{"hard_reject": false}`` or per-field
  ``{"field": {"op": value}}`` with ``eq``, ``ne``, ``gt``, ``gte``, ``lt``, ``lte``,
  ``in``, ``not_in``, ``contains``, ``is_null``.
- Projection: omit ``include_fields`` → each row is **``id`` only** (slim default).
  ``include_fields`` / ``exclude_fields``: JSON list **or** comma-separated string.
  Macros: ``all``, ``all_transition_fields``, ``transition_fields``, ``all_track_fields``,
  ``track_fields``, ``all_feature_fields``, ``feature_fields``. Add ``id`` explicitly
  when using track/feature macros if you need the transition row id in each row.
- ``include_stats`` (default **true**): aggregates over the filtered slice; set
  **false** for smaller JSON.
- ``include_field_catalog`` (default **false**): adds ``fields.available``,
  ``fields.groups``, ``include_macros``, top-level ``filter_operators`` (large).
- ``target_quality`` (optional 0..1): adds explicit feasibility verdict in
  ``quality_guardrail``:
  - ``max_overall_quality`` — observed ceiling in the filtered slice
  - ``meets_target`` — whether ceiling reaches your target
  - ``non_reject_rows_at_or_above_target`` — usable rows count at/above target

**``explain_transition``** (``from_track_id``, ``to_track_id``) — narrative breakdown
(may differ from DB until the pair is scored with ``score_transitions``).

**Resources:** ``transition://<from_track_id>/<to_track_id>/score`` and
``.../recipe`` (numeric ids in the path).
---
""".strip()


DRAFT_STATELESS_GUIDE = """
---
### Draft workflow in stateless clients (CLI / one-shot calls)

Session state may not persist across independent calls. For deterministic flows:
- Prefer ``preview_draft(track_ids=[...], template="...")`` over state-only preview.
- Prefer ``commit_draft(track_ids=[...], set_name="...", template="...")`` over
  relying on previously stored session state.
- Use ``update_set_draft`` only when you are sure calls are in the same MCP session.
---
""".strip()


def message_user(content: str) -> Message:
    return Message(content, role="user")


def message_assistant(content: str) -> Message:
    return Message(content, role="assistant")


def prompt_pair(user_content: str, assistant_content: str) -> list[Message]:
    """Two-turn pattern: instructions (user) + kickoff line (assistant)."""
    return [message_user(user_content), message_assistant(assistant_content)]


def make_prompt_result(messages: list[Message], description: str) -> PromptResult:
    return PromptResult(messages=messages, description=description)
