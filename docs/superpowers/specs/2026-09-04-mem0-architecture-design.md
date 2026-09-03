# Mem0 Architecture Design

**Goal:** Make Mem0 the shared long-term memory backend for the DJ Music project and AI coding agents, with explicit scopes, proactive retrieval, durable-only capture, and no secrets in memory.

## Decision

Use **Mem0 Platform** as the single memory backend. Use the Mem0 SDK/API from application code and the official OpenCode Mem0 plugin for OpenCode lifecycle integration. Use the hosted Mem0 MCP server only for other MCP clients or environments that need tool-level memory access; do not register both the plugin's native tools and the same Mem0 MCP server in one OpenCode instance.

## Scopes

- `project`: repository knowledge and engineering decisions, keyed by stable `app_id`.
- `personal`: user preferences within the project, keyed by stable `user_id` + `app_id`.
- `session`: transient run context keyed by `run_id`; never treat it as durable project knowledge.
- `global`: explicit opt-in cross-project retrieval only.

For this repository the project identity is `evgenygurin-dj-music-plugin`. The user identity must be configured explicitly and must never contain a credential.

## Retrieval

For every substantial task, perform a read-only project-scoped retrieval even when the memory count is currently zero. Prefer a semantic query plus a narrow category query. Deduplicate results and inject at most five concise memories into model context. Retrieval must fail open: a Mem0 outage must not block normal work.

## Capture

Capture only durable information: architecture decisions, stable conventions, dependencies, reproducible debugging findings, deployment constraints, security constraints, and stable preferences. Do not store credentials, tokens, passwords, raw `.env`, large logs, source dumps, temporary state, or speculation. Capture must be asynchronous and non-blocking where possible.

## Maintainability

Do not patch `node_modules/@mem0/opencode-plugin/dist/index.js` as the final solution. Keep vendor dependencies immutable and put project-specific policy in a maintainable local OpenCode plugin/policy layer. Preserve the official Mem0 native tools and skills.

## Verification

Verify configuration loading, project identity, proactive retrieval on an empty scope, durable capture classification, secret redaction, failure-open behavior, and a real add/search/delete round trip using a synthetic test memory that is removed after the test.
