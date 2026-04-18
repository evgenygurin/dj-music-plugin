---
description: LLM sampling modes for AI-assisted workflows
globs: app/server/sampling.py
---

# LLM Sampling

Two modes для AI-assisted дискавери (v1 — через prompt `expand_playlist_workflow`, нет отдельного `find_similar_tracks` tool'а):

## 1. Client-driven (default — Claude Code MAX)

Claude Code IS the LLM. Prompt `expand_playlist_workflow` ведёт его по шагам:

```text
1. provider_search(provider="yandex", query="Amelie Lens acid techno", type="tracks", limit=20)
2. provider_read(provider="yandex", entity="track_similar", id=<seed_track_id>)
3. entity_create(entity="track", data={ym_id: ...})           # через track_import handler
4. entity_create(entity="track_features", data={track_ids, level: 2})
5. audit / filter / playlist_sync (opcional)
```

**Why**: Claude Code doesn't support MCP sampling (`createMessage`) — `ctx.sample()` can't call back to the client.

## 2. Server-side (requires `DJ_ANTHROPIC_API_KEY`)

`ctx.sample()` calls Anthropic API via fallback handler в `app/server/sampling.py`. Используется только в headless/automated scenarios (не Claude Code).

## Gotchas

- `ctx.sample()` does NOT work in Claude Code — always use client-driven mode (prompt + manual `provider_*` calls).
- Client-driven mode requires the caller to be an LLM (Claude Code, not a script).
- Per-session token budget enforced by `SamplingBudgetMiddleware` (`app/server/middleware/sampling_budget.py`).
