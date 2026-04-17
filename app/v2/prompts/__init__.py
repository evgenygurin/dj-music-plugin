"""FastMCP workflow prompts for v2.

All prompts return ``fastmcp.prompts.PromptResult`` — the v3 type.
Prompts must NOT import repositories, tools, or providers directly — they
are pure text builders chaining the Phase 3 tool surface.
"""
