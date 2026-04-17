"""dj_expert_session — knowledge priming recipe.

Points the LLM at ``reference://*`` blobs so it acquires DJ-domain
vocabulary (Camelot, 15 subgenres, 8 templates, audit rules) in one call.
"""

from __future__ import annotations

from fastmcp.prompts import Message, PromptResult, prompt

from app.v2.prompts._shared import PROMPT_META

_BODY = """You are a DJ techno set-building expert.

Load domain knowledge before planning any mix. Read these resources
once per session:

1. reference://camelot      — 24-key Camelot wheel + distance rules
2. reference://subgenres    — 15 techno subgenres (ambient_dub -> hard_techno)
3. reference://templates    — 8 set templates (warm_up_30 .. full_library)
4. reference://audit_rules  — techno quality criteria (BPM, LUFS, spectral)

Apply these guidelines:
- BPM range for techno: 120-155 (sweet spot 124-132).
- Prefer Camelot distance 0-1 between adjacent tracks (same key, +/-1 on wheel, or A<->B relative).
- Energy flow follows the target template's arc — don't peak too early.
- Mood transitions: stay within one step of the 15-subgenre order,
  or cross deliberately for contrast.

Inspect the library with entity_list / entity_get, score candidate
pairs with transition_score_pool, order with sequence_optimize, then
persist via entity_create(entity='set_version').
"""


@prompt(
    name="dj_expert_session",
    description=(
        "Prime the LLM with DJ-domain knowledge (Camelot, subgenres, templates, audit rules)."
    ),
    tags={"namespace:workflow", "priming"},
    meta=PROMPT_META,
)
def dj_expert_session() -> PromptResult:
    return PromptResult(
        messages=[Message(_BODY)],
        description="DJ Expert Session — knowledge priming for techno set building.",
    )
