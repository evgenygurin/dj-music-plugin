# Cell 12 — Mem0 / Agent Memory

## Mission
Own the current Mem0/OpenCode memory integration and prove that memory tools are actually invoked.

## Read
- `.opencode/mem0-policy.js`
- `.opencode/tests/**`
- `.opencode/agents/**`, `.opencode/opencode.json`
- `docs/MEM0_BEST_PRACTICES.md`
- current Mem0 architecture spec/plan

## Scope
- Memory policy, lifecycle and invocation rules.
- `search_memories` / `add_memory` runtime evidence where supported.
- Avoid accidental memory writes, recursion, or secret leakage.
- Align agent instructions with existing repository governance.

## Write ownership
- `.opencode/mem0-policy.js`
- `.opencode/tests/**`
- Mem0-specific docs/specs only.

## Constraints
- Preserve unrelated OpenCode changes in the worktree.
- Do not invent runtime success without execution evidence.
- Do not expose credentials or private memory content.

## Deliverable
`REPORT.md` with invocation evidence, tests, risks, and integration requirements.