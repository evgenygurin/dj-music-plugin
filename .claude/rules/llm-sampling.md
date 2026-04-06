---
description: LLM sampling modes for AI-assisted tools
globs: app/mcp/tools/discovery.py
---

# LLM Sampling

Two modes for LLM-assisted tools (`find_similar_tracks` strategy="llm"):

## 1. Client-driven (default — Claude Code MAX)

Claude Code IS the LLM — it generates search queries and passes them as tool params:

```python
find_similar_tracks(
    track_id=42,
    strategy="llm",
    search_queries=["Amelie Lens acid techno", "FJAAK industrial"]
)
```

Use prompt `llm_discovery_workflow` for step-by-step instructions.

**Why**: Claude Code doesn't support MCP sampling (`createMessage`) — `ctx.sample()` can't call back to the client.

## 2. Server-side (requires `DJ_ANTHROPIC_API_KEY`)

`ctx.sample()` calls Anthropic API via fallback handler. For headless/automated scenarios.

## Gotchas

- `ctx.sample()` does NOT work in Claude Code — always use client-driven mode
- Client-driven mode requires the caller to be an LLM (Claude Code, not a script)
