"""FastMCP workflow prompts for v2.

All prompts return ``fastmcp.prompts.PromptResult`` — the v3 type.
Prompts must NOT import repositories, tools, or providers directly — they
are pure text builders chaining the Phase 3 tool surface.

Modules in this package (all discovered by FSP). Workflow prompts cover
the full DJ lifecycle — see
``docs/research/2026-06-22-techno-set-construction-and-mcp-prompts.md`` for
the design rationale.

Core (6):

- ``dj_expert_session``        — knowledge priming over ``reference://*``
- ``build_set_workflow``       — 8-step recipe (list -> optimize -> persist)
- ``deliver_set_workflow``     — export + optional YM sync with conflict gate
- ``expand_playlist_workflow`` — audit -> discover -> import -> analyze
- ``full_pipeline``            — chain expand + build + deliver
- ``quick_mix_check``          — pair compatibility shortcut

Library & analysis (2):

- ``library_health_workflow``  — coverage + BPM/key/mood spread + audit fails
- ``analyze_library_workflow`` — batch-analyze / upgrade tier

Set design (5):

- ``harmonic_journey_workflow``  — Camelot key journey (harmonic mixing)
- ``subgenre_journey_workflow``  — energy-axis subgenre journey
- ``scenario_set_workflow``      — warmup/peak/closing/roller/wave/progressive
- ``b2b_planning_workflow``      — back-to-back across two crates
- ``extend_set_workflow``        — lengthen a set, keep the arc

Set repair (3):

- ``set_review_workflow``      — critique + fix an existing set
- ``fix_transition_workflow``  — diagnose/repair one weak/hard transition
- ``replace_track_workflow``   — swap a weak slot for a better candidate

Discovery & ops (3):

- ``crate_digging_workflow``   — discovery-first digging + curation
- ``taste_profile_workflow``   — feedback/affinity taste memory
- ``playlist_sync_workflow``   — pull/push/diff with YM (conflict gate)

Generation (2):

- ``suno_set_asset_workflow``  — enrich tracks: gap fills, texture, bridges
- ``suno_track_production_workflow`` — full Suno track / vocal production

Prompts are pure text-builders — they MUST NOT import repositories, tools,
or providers. Every entity / provider / field-preset name referenced in a
prompt body is pinned by
``tests/prompts/test_prompt_content_correctness.py``.
"""
