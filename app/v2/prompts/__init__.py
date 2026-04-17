"""FastMCP workflow prompts for v2.

All prompts return ``fastmcp.prompts.PromptResult`` — the v3 type.
Prompts must NOT import repositories, tools, or providers directly — they
are pure text builders chaining the Phase 3 tool surface.

Modules in this package (all discovered by FSP in Phase 5):

- ``dj_expert_session``        — knowledge priming over ``reference://*``
- ``build_set_workflow``       — 8-step recipe (list -> optimize -> persist)
- ``deliver_set_workflow``     — export + optional YM sync with conflict gate
- ``expand_playlist_workflow`` — audit -> discover -> import -> analyze
- ``full_pipeline``            — chain expand + build + deliver
- ``quick_mix_check``          — pair compatibility shortcut

Phase 5 TODO: ``app/v2/server/app.py:build_mcp_app_for_tests`` must point
FileSystemProvider at ``app/v2/prompts/`` so these decorators register.
The registration xfails in ``tests/v2/prompts/`` flip to pass once that
wiring lands.
"""
